import json
from pathlib import Path

import mlflow
import pytest
from ml.models.skill_predictor import build_pipeline

from ml.models.skill_predictor import train_skill_model
from ml.tracking import mlflow_tracker
from ml.training.skill_dataset import synthetic_training_rows
from ml.features.skill_features import training_frame, NUMERIC_FEATURES, CATEGORICAL_FEATURES


def _small_model():
    rows = synthetic_training_rows()
    frame = training_frame(rows)
    x = frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = frame["target_skill"]
    model = build_pipeline().set_params(classifier__n_estimators=3).fit(x, y)
    return model


def test_experiment_configuration_is_stable():
    assert mlflow_tracker.EXPERIMENT_NAME == "AI-Coding-Mentor-Skill-Prediction"
    assert mlflow_tracker.REGISTERED_MODEL_NAME == "AI-Coding-Mentor-Skill-Predictor"
    assert mlflow_tracker.configured_tracking_uri()


def test_local_tracking_logs_parameters_metrics_tags_and_model(tmp_path):
    model = _small_model()
    metadata = {
        "model_name": "RandomForestClassifier",
        "model_version": "skill-model-v1",
        "feature_version": "features-v1",
        "feature_names": NUMERIC_FEATURES + CATEGORICAL_FEATURES,
        "training_source": "synthetic_development_data",
        "training_sample_count": 30,
        "class_labels": ["advanced", "beginner", "intermediate"],
    }
    outcome = mlflow_tracker.track_training_run(
        model=model,
        metadata=metadata,
        params={"random_state": 42, "test_size": 0.2, "n_estimators": 3},
        metrics={"accuracy": 0.8, "precision": 0.8, "recall": 0.8, "f1_score": 0.8},
        tracking_uri=mlflow_tracker.local_tracking_uri(tmp_path),
        experiment_name="test-skill-experiment",
        registered_model_name=None,
    )
    assert outcome["status"] == "tracked"
    assert outcome["run_id"]
    client = mlflow.tracking.MlflowClient(tracking_uri=outcome["tracking_uri"])
    run = client.get_run(outcome["run_id"])
    assert run.data.params["random_state"] == "42"
    assert run.data.params["training_source"] == "synthetic_development_data"
    assert run.data.metrics["f1_score"] == pytest.approx(0.8)
    assert run.data.tags["feature_version"] == "features-v1"
    artifacts = client.list_artifacts(outcome["run_id"])
    assert "skill_metadata.json" in {item.path for item in artifacts}
    assert outcome["model_uri"]
    assert mlflow.models.get_model_info(outcome["model_uri"]).flavors["sklearn"]


def test_remote_unavailable_falls_back_to_file_store(monkeypatch, tmp_path):
    original = mlflow_tracker._log_run
    calls = 0

    def fail_remote_then_track_local(**kwargs):
        nonlocal calls
        calls += 1
        if kwargs["tracking_uri"].startswith("http:"):
            raise RuntimeError("server unavailable")
        return {"status": "tracked", "tracking_uri": kwargs["tracking_uri"], "run_id": "real-local-run"}

    monkeypatch.setattr(mlflow_tracker, "_log_run", fail_remote_then_track_local)
    outcome = mlflow_tracker.track_training_run(
        model=object(),
        metadata={"model_version": "skill-model-v1", "feature_version": "features-v1", "training_source": "synthetic_development_data", "feature_names": [], "class_labels": []},
        params={"random_state": 42},
        metrics={"accuracy": 1.0},
        tracking_uri="http://127.0.0.1:1",
        experiment_name="fallback-test-experiment",
        registered_model_name=None,
        fallback_dir=tmp_path,
    )
    assert outcome["status"] == "tracked"
    assert outcome["fallback_used"] is True
    assert outcome["tracking_uri"].startswith("file:")
    assert outcome["run_id"]
    assert calls == 2


def test_tracking_failure_does_not_create_fake_run_id(monkeypatch, tmp_path):
    monkeypatch.setattr(mlflow_tracker, "_log_run", lambda **_: (_ for _ in ()).throw(RuntimeError("tracking unavailable")))
    result = mlflow_tracker.track_training_run(
        model=object(),
        metadata={"model_version": "skill-model-v1"},
        params={},
        metrics={},
        tracking_uri="http://127.0.0.1:1",
        fallback_dir=tmp_path,
    )
    assert result["status"] == "unavailable"
    assert "run_id" not in result


def test_training_keeps_local_joblib_and_metadata(tmp_path):
    output = train_skill_model(artifact_dir=tmp_path, enable_tracking=False)
    assert output["model_path"].exists()
    assert output["metadata_path"].exists()
    metadata = json.loads(output["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["training_source"] == "synthetic_development_data"
    assert metadata["model_version"] == "skill-model-v1"
    assert metadata["mlflow"]["status"] == "disabled"
    assert metadata["metrics"]["f1"] == pytest.approx(1.0)
