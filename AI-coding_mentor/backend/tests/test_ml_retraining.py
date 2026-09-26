import csv
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import joblib
import pytest

from ml.data.generate_synthetic_dataset import generate_dataset
from ml.data.prepare_skill_dataset import prepare_dataset
from ml.features.skill_features import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from ml.models.skill_predictor import train_skill_model
from ml.monitoring.baseline import create_monitoring_baseline
from ml.retraining.artifact_promoter import ArtifactPromoter
from ml.retraining.promotion_gate import evaluate_promotion_gate
from ml.retraining.retraining_service import (
    RetrainingDataError,
    RetrainingService,
    load_and_validate_training_data,
)
from ml.retraining.retraining_trigger import determine_retraining_need
from ml.retraining.rollback_service import RollbackService
from ml.retraining.versions import next_baseline_version, next_model_version
from ml.serving.skill_model_service import SkillModelService


class FakeMonitoringService:
    def __init__(self, report=None):
        self.report = report or {"status": "stable", "drifted_features": []}

    def get_report(self):
        return self.report


@pytest.fixture(scope="module")
def training_bundle(tmp_path_factory):
    root = tmp_path_factory.mktemp("retraining-template")
    raw_path = root / "raw" / "training.csv"
    data_path = root / "data" / "processed" / "skill_training_data_processed.csv"
    dataset_metadata_path = data_path.parent / "dataset_metadata.json"
    generate_dataset(raw_path)
    dataset_metadata = prepare_dataset(raw_path, data_path, dataset_metadata_path)
    with data_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
    train_rows = []
    for row in rows:
        train_rows.append({
            **{name: float(row[name]) if name != "attempt_count" else int(row[name]) for name in NUMERIC_FEATURES},
            **{name: row[name] for name in CATEGORICAL_FEATURES},
            "target_skill": row["skill_level"],
        })
    original_artifacts = train_skill_model(
        rows=train_rows,
        source="synthetic_development_data",
        artifact_dir=root / "active",
        enable_tracking=False,
    )
    baseline_path = root / "active" / "monitoring_baseline.json"
    baseline = create_monitoring_baseline(
        data_path=data_path,
        dataset_metadata_path=dataset_metadata_path,
        model_path=original_artifacts["model_path"],
        model_metadata_path=original_artifacts["metadata_path"],
        output_path=baseline_path,
    )
    return {
        "root": root,
        "data_path": data_path,
        "dataset_metadata_path": dataset_metadata_path,
        "dataset_metadata": dataset_metadata,
        "source_model": original_artifacts["model_path"],
        "source_metadata": original_artifacts["metadata_path"],
        "source_baseline": baseline_path,
        "baseline": baseline,
    }


@pytest.fixture
def retraining_context(tmp_path, training_bundle):
    active_dir = tmp_path / "artifacts"
    active_dir.mkdir()
    model_path = active_dir / "skill_model.joblib"
    metadata_path = active_dir / "skill_metadata.json"
    baseline_path = active_dir / "monitoring_baseline.json"
    shutil.copy2(training_bundle["source_model"], model_path)
    shutil.copy2(training_bundle["source_metadata"], metadata_path)
    shutil.copy2(training_bundle["source_baseline"], baseline_path)
    candidate_dir = active_dir / "candidates"
    backups_dir = active_dir / "backups"
    report_path = active_dir / "retraining_report.json"

    def serving_reloader(*, expected_model_version=None):
        service = SkillModelService(model_path=model_path, metadata_path=metadata_path)
        assert service.ready
        assert service.model_version == expected_model_version
        return service

    promoter = ArtifactPromoter(
        model_path=model_path,
        metadata_path=metadata_path,
        baseline_path=baseline_path,
        backup_dir=backups_dir,
        serving_reloader=serving_reloader,
    )
    service = RetrainingService(
        dataset_path=training_bundle["data_path"],
        model_path=model_path,
        metadata_path=metadata_path,
        baseline_path=baseline_path,
        candidate_dir=candidate_dir,
        report_path=report_path,
        monitoring_service=FakeMonitoringService(),
        artifact_promoter=promoter,
    )
    return {
        "service": service,
        "model_path": model_path,
        "metadata_path": metadata_path,
        "baseline_path": baseline_path,
        "candidate_dir": candidate_dir,
        "backups_dir": backups_dir,
        "report_path": report_path,
        "original_model_bytes": model_path.read_bytes(),
        "original_metadata_bytes": metadata_path.read_bytes(),
        "original_baseline_bytes": baseline_path.read_bytes(),
        "promoter": promoter,
        "serving_reloader": serving_reloader,
        "training_bundle": training_bundle,
    }


def test_training_data_validation_accepts_versioned_processed_dataset(training_bundle):
    frame, metadata = load_and_validate_training_data(training_bundle["data_path"], minimum_samples=30)

    assert len(frame) == 150
    assert set(frame["target_skill"]) == {"beginner", "intermediate", "advanced"}
    assert metadata["dataset_version"] == "dataset-v1"


def test_missing_dataset_is_rejected(tmp_path):
    with pytest.raises(RetrainingDataError, match="dataset is missing"):
        load_and_validate_training_data(tmp_path / "absent.csv", minimum_samples=30)


def test_missing_required_columns_are_rejected(tmp_path):
    dataset_path = tmp_path / "partial.csv"
    dataset_path.write_text("skill_level\nbeginner\n", encoding="utf-8")
    (tmp_path / "dataset_metadata.json").write_text('{"dataset_version":"dataset-v1"}', encoding="utf-8")

    with pytest.raises(RetrainingDataError, match="missing required columns"):
        load_and_validate_training_data(dataset_path, minimum_samples=1)


def test_missing_skill_class_is_rejected(training_bundle, tmp_path):
    dataset_path = tmp_path / "missing_class.csv"
    with training_bundle["data_path"].open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames
        rows = list(reader)
    rows = [row for row in rows if row["skill_level"] != "advanced"]
    with dataset_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (tmp_path / "dataset_metadata.json").write_text(
        json.dumps({"dataset_version": "dataset-v1", "row_count": len(rows)}),
        encoding="utf-8",
    )

    with pytest.raises(RetrainingDataError, match="must contain beginner, intermediate, and advanced"):
        load_and_validate_training_data(dataset_path, minimum_samples=30)


def test_drift_requests_retraining_and_insufficient_data_does_not():
    drift = determine_retraining_need({"status": "drift", "drifted_features": ["language"]})
    insufficient = determine_retraining_need(
        {"status": "insufficient_data"},
        new_training_rows=1000,
    )
    forced = determine_retraining_need({"status": "insufficient_data"}, force=True)

    assert drift == {"retrain_required": True, "reason": "feature_drift", "drifted_features": ["language"]}
    assert insufficient["retrain_required"] is False
    assert insufficient["reason"] == "insufficient_monitoring_data"
    assert forced["retrain_required"] is True
    assert forced["reason"] == "manual"


def test_new_data_trigger_requires_configured_delta():
    decision = determine_retraining_need(
        {"status": "stable"},
        new_training_rows=30,
        minimum_new_rows=30,
    )
    assert decision["retrain_required"] is True
    assert decision["reason"] == "new_training_data"


def test_model_and_baseline_versions_increment_deterministically():
    assert next_model_version("skill-model-v1") == "skill-model-v2"
    assert next_model_version("skill-model-v9") == "skill-model-v10"
    assert next_baseline_version("baseline-v1") == "baseline-v2"
    with pytest.raises(ValueError, match="Unsupported model version"):
        next_model_version("other-model")


def test_candidate_training_is_separate_and_uses_same_validation_rows(monkeypatch, retraining_context):
    from ml.retraining import retraining_service as service_module

    evaluated_indexes = []
    original_evaluate = service_module.evaluate_model

    def capture_validation(model, x_valid, y_valid):
        evaluated_indexes.append((tuple(x_valid.index), tuple(y_valid.index)))
        return original_evaluate(model, x_valid, y_valid)

    monkeypatch.setattr(service_module, "evaluate_model", capture_validation)
    report = retraining_context["service"].run(
        force=True,
        enable_mlflow=False,
    )

    candidate_model_path = retraining_context["candidate_dir"] / "skill_model_candidate.joblib"
    assert report["status"] == "promoted"
    assert candidate_model_path.is_file()
    assert candidate_model_path != retraining_context["model_path"]
    assert len(evaluated_indexes) == 2
    assert evaluated_indexes[0] == evaluated_indexes[1]
    assert report["candidate_metrics"]["validation_sample_count"] == 30
    assert report["current_metrics"]["validation_sample_count"] == 30
    assert report["candidate_metrics"]["accuracy"] >= 0.6


def test_below_gate_candidate_is_rejected_without_replacing_current_model(retraining_context):
    retraining_context["service"].minimum_accuracy = 1.01

    report = retraining_context["service"].run(force=True, enable_mlflow=False)

    assert report["status"] == "rejected"
    assert report["rejection_reason"] == "candidate_failed_quality_gate"
    assert retraining_context["model_path"].read_bytes() == retraining_context["original_model_bytes"]
    assert retraining_context["metadata_path"].read_bytes() == retraining_context["original_metadata_bytes"]
    assert retraining_context["baseline_path"].read_bytes() == retraining_context["original_baseline_bytes"]


def test_accepted_candidate_is_promoted_backed_up_and_versions_match(retraining_context):
    report = retraining_context["service"].run(force=True, enable_mlflow=False)
    metadata = json.loads(retraining_context["metadata_path"].read_text(encoding="utf-8"))
    baseline = json.loads(retraining_context["baseline_path"].read_text(encoding="utf-8"))
    serving = retraining_context["serving_reloader"](expected_model_version="skill-model-v2")

    assert report["status"] == "promoted"
    assert report["old_model_version"] == "skill-model-v1"
    assert report["candidate_model_version"] == "skill-model-v2"
    assert metadata["model_version"] == serving.model_version == baseline["model_version"] == "skill-model-v2"
    assert metadata["feature_version"] == serving.feature_version == baseline["feature_version"] == "features-v1"
    assert baseline["baseline_version"] == "baseline-v2"
    assert metadata["dataset_version"] == baseline["dataset_version"] == "dataset-v1"
    assert report["mlflow"]["status"] == "disabled"
    assert report["backup_files"]
    assert (retraining_context["backups_dir"] / "skill_model_skill-model-v1.joblib").exists()
    assert (retraining_context["backups_dir"] / "skill_metadata_skill-model-v1.json").exists()
    assert (retraining_context["backups_dir"] / "monitoring_baseline_baseline-v1.json").exists()


def test_rollback_restores_model_metadata_and_monitoring_baseline(retraining_context):
    promoted = retraining_context["service"].run(force=True, enable_mlflow=False)
    assert promoted["status"] == "promoted"
    rollback = RollbackService(
        backup_dir=retraining_context["backups_dir"],
        metadata_path=retraining_context["metadata_path"],
        promoter=retraining_context["promoter"],
    )

    result = rollback.rollback_to_version("skill-model-v1")

    metadata = json.loads(retraining_context["metadata_path"].read_text(encoding="utf-8"))
    baseline = json.loads(retraining_context["baseline_path"].read_text(encoding="utf-8"))
    service = retraining_context["serving_reloader"](expected_model_version="skill-model-v1")
    assert result["status"] == "rolled_back"
    assert metadata["model_version"] == service.model_version == baseline["model_version"] == "skill-model-v1"
    assert metadata["feature_version"] == service.feature_version == baseline["feature_version"] == "features-v1"
    assert retraining_context["model_path"].read_bytes() == retraining_context["original_model_bytes"]
    assert retraining_context["metadata_path"].read_bytes() == retraining_context["original_metadata_bytes"]
    assert retraining_context["baseline_path"].read_bytes() == retraining_context["original_baseline_bytes"]
    assert result["backup_files"]


def test_failed_serving_reload_restores_previous_artifact_triple(retraining_context):
    original_reloader = retraining_context["serving_reloader"]

    def fail_candidate_reload(*, expected_model_version):
        if expected_model_version == "skill-model-v2":
            raise RuntimeError("simulated serving reload failure")
        return original_reloader(expected_model_version=expected_model_version)

    retraining_context["promoter"]._serving_reloader = fail_candidate_reload

    report = retraining_context["service"].run(force=True, enable_mlflow=False)

    assert report["status"] == "failed"
    assert retraining_context["model_path"].read_bytes() == retraining_context["original_model_bytes"]
    assert retraining_context["metadata_path"].read_bytes() == retraining_context["original_metadata_bytes"]
    assert retraining_context["baseline_path"].read_bytes() == retraining_context["original_baseline_bytes"]
    assert original_reloader(expected_model_version="skill-model-v1").model_version == "skill-model-v1"


def test_insufficient_monitoring_report_does_not_create_candidate(retraining_context):
    report = retraining_context["service"].run(
        monitoring_report={"status": "insufficient_data"},
        enable_mlflow=False,
    )

    assert report["status"] == "not_required"
    assert report["trigger"] == "insufficient_monitoring_data"
    assert report["candidate_model_version"] is None
    assert not (retraining_context["candidate_dir"] / "skill_model_candidate.joblib").exists()


def test_missing_dataset_returns_failed_report_without_touching_active_model(retraining_context, tmp_path):
    retraining_context["service"].dataset_path = tmp_path / "missing.csv"

    report = retraining_context["service"].run(force=True, enable_mlflow=False)

    assert report["status"] == "failed"
    assert "dataset is missing" in report["error"]
    assert retraining_context["model_path"].read_bytes() == retraining_context["original_model_bytes"]
    assert json.loads(retraining_context["report_path"].read_text(encoding="utf-8"))["status"] == "failed"


def test_candidate_mlflow_is_explicitly_disabled_in_offline_mode(retraining_context):
    report = retraining_context["service"].run(force=True, enable_mlflow=False)

    assert report["status"] == "promoted"
    assert report["mlflow"] == {
        "status": "disabled",
        "reason": "Explicit offline/test mode; candidate was not registered",
    }
    assert json.loads(retraining_context["report_path"].read_text(encoding="utf-8"))["dataset_version"] == "dataset-v1"


def test_unavailable_mlflow_is_reported_without_claiming_registration(monkeypatch, retraining_context):
    from ml.tracking import mlflow_tracker

    monkeypatch.setattr(
        mlflow_tracker,
        "track_training_run",
        lambda **_: {"status": "unavailable", "reason": "server and local tracking unavailable"},
    )

    report = retraining_context["service"].run(force=True, enable_mlflow=True)

    assert report["status"] == "promoted"
    assert report["mlflow"]["status"] == "unavailable"
    assert "registry_status" not in report["mlflow"]


def test_gate_requires_candidate_quality_and_non_degrading_accuracy():
    candidate = {"accuracy": 0.7, "precision": 0.7, "recall": 0.7, "f1": 0.7, "validation_sample_count": 30}
    current = {"accuracy": 0.7, "precision": 0.7, "recall": 0.7, "f1": 0.7, "validation_sample_count": 30}
    accepted = evaluate_promotion_gate(candidate, current, minimum_accuracy=0.6, minimum_f1=0.6)
    degraded = evaluate_promotion_gate({**candidate, "accuracy": 0.69}, current, minimum_accuracy=0.6, minimum_f1=0.6)

    assert accepted["accepted"] is True
    assert degraded["accepted"] is False
    assert "candidate_accuracy_not_below_current" in degraded["failed_checks"]
