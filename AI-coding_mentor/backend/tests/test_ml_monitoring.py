import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import security
from ml.data.generate_synthetic_dataset import generate_dataset
from ml.data.prepare_skill_dataset import prepare_dataset
from ml.features.skill_features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, training_frame
from ml.models.skill_predictor import train_skill_model
from ml.monitoring.baseline import create_monitoring_baseline
from ml.monitoring.drift_detector import (
    DRIFT_THRESHOLD,
    WARNING_THRESHOLD,
    compare_categorical_feature,
    compare_numeric_feature,
    compare_prediction_distribution,
)
from ml.monitoring.monitoring_service import MonitoringService, get_monitoring_service
from ml.monitoring.prediction_logger import PredictionLogger
from ml.monitoring import prediction_logger
from ml.serving import skill_model_service
from ml.training.skill_dataset import synthetic_training_rows


class FakeCursor(list):
    def sort(self, key, direction):
        self[:] = sorted(self, key=lambda row: row.get(key), reverse=direction < 0)
        return self

    def limit(self, count):
        del self[count:]
        return self


class FakePredictionCollection:
    def __init__(self, records=None):
        self.records = list(records or [])
        self.inserted = []
        self.query = None
        self.projection = None

    def insert_one(self, document):
        self.inserted.append(document)
        self.records.append(document)
        return SimpleNamespace(inserted_id=document["prediction_id"])

    def find(self, query, projection):
        self.query = query
        self.projection = projection
        return FakeCursor([
            record for record in self.records
            if all(record.get(key) == value for key, value in query.items())
        ])


@pytest.fixture(scope="module")
def monitoring_fixture(tmp_path_factory):
    root = tmp_path_factory.mktemp("monitoring-baseline")
    raw_path = root / "raw.csv"
    processed_path = root / "processed" / "skill_training_data_processed.csv"
    dataset_metadata_path = processed_path.parent / "dataset_metadata.json"
    artifacts_path = root / "artifacts"
    model_artifacts = train_skill_model(
        rows=synthetic_training_rows(),
        source="synthetic_development_data",
        artifact_dir=artifacts_path,
        enable_tracking=False,
    )
    generate_dataset(raw_path)
    dataset_metadata = prepare_dataset(raw_path, processed_path, dataset_metadata_path)
    baseline_path = artifacts_path / "monitoring_baseline.json"
    baseline = create_monitoring_baseline(
        data_path=processed_path,
        dataset_metadata_path=dataset_metadata_path,
        model_path=model_artifacts["model_path"],
        model_metadata_path=model_artifacts["metadata_path"],
        output_path=baseline_path,
    )
    with processed_path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    feature_rows = [
        {
            **{feature: float(row[feature]) for feature in NUMERIC_FEATURES},
            **{feature: row[feature] for feature in CATEGORICAL_FEATURES},
        }
        for row in rows
    ]
    feature_frame = training_frame(feature_rows)[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    predictions = model_artifacts["model"].predict(feature_frame)
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = [
        {
            "prediction_id": f"baseline-{index}",
            "timestamp": base_time + timedelta(seconds=index),
            "model_version": baseline["model_version"],
            "feature_version": baseline["feature_version"],
            "language": row["language"],
            "topic": row["topic"],
            "prediction": str(predictions[index]),
            "features": {feature: feature_rows[index][feature] for feature in NUMERIC_FEATURES},
        }
        for index, row in enumerate(rows)
    ]
    return {
        "root": root,
        "baseline": baseline,
        "baseline_path": baseline_path,
        "dataset_metadata": dataset_metadata,
        "records": records,
        "model_artifacts": model_artifacts,
    }


def _fake_model_service(metadata):
    return SimpleNamespace(
        ready=True,
        model_version=metadata["model_version"],
        feature_version=metadata["feature_version"],
        metadata={"training_sample_count": metadata["model_training_sample_count"]},
    )


def _service(fixture, records, minimum=30, window=500):
    collection = FakePredictionCollection(records)
    service = MonitoringService(
        baseline_path=fixture["baseline_path"],
        prediction_collection_provider=lambda: collection,
        model_service_provider=lambda: _fake_model_service(fixture["baseline"]),
        minimum_predictions=minimum,
        window_size=window,
    )
    return service, collection


def test_baseline_generation_is_deterministic_and_contains_feature_statistics(monitoring_fixture, tmp_path):
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    inputs = {
        "data_path": monitoring_fixture["root"] / "processed" / "skill_training_data_processed.csv",
        "dataset_metadata_path": monitoring_fixture["root"] / "processed" / "dataset_metadata.json",
        "model_path": monitoring_fixture["model_artifacts"]["model_path"],
        "model_metadata_path": monitoring_fixture["model_artifacts"]["metadata_path"],
    }

    first = create_monitoring_baseline(**inputs, output_path=first_path)
    create_monitoring_baseline(**inputs, output_path=second_path)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert first["baseline_version"] == "baseline-v1"
    assert first["dataset_version"] == monitoring_fixture["dataset_metadata"]["dataset_version"]
    assert first["model_version"] == "skill-model-v1"
    assert first["feature_version"] == "features-v1"
    assert first["sample_count"] == 150
    assert set(first["numeric_features"]) == set(NUMERIC_FEATURES)
    assert set(first["categorical_features"]) == set(CATEGORICAL_FEATURES)
    for feature in NUMERIC_FEATURES:
        stats = first["numeric_features"][feature]
        assert {"mean", "standard_deviation", "minimum", "maximum", "quantiles", "histogram"}.issubset(stats)
    assert first["prediction_distribution"]["counts"]


def test_repository_ignore_rules_allow_versioned_baseline():
    ignore_text = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "ml/artifacts/*.json" in ignore_text
    assert "!ml/artifacts/monitoring_baseline.json" in ignore_text


def test_stable_synthetic_window_reports_no_drift(monitoring_fixture):
    service, _ = _service(monitoring_fixture, monitoring_fixture["records"])

    report = service.get_report()

    assert report["status"] == "stable"
    assert report["prediction_count"] == 150
    assert report["drifted_features"] == []
    assert report["warning_features"] == []
    assert report["prediction_drift"]["status"] == "stable"
    assert report["monitoring_window"]["type"] == "last_n_predictions"
    assert "not a general model-health" in report["scope_note"]


def test_numeric_distribution_shift_is_detected(monitoring_fixture):
    records = [dict(record, features={**record["features"], "assessment_accuracy": 10.0}) for record in monitoring_fixture["records"]]
    service, _ = _service(monitoring_fixture, records)

    report = service.get_report()

    drift = next(item for item in report["feature_drift"] if item["feature"] == "assessment_accuracy")
    assert drift["drift_score"] >= DRIFT_THRESHOLD
    assert drift["status"] == "drift"
    assert "assessment_accuracy" in report["drifted_features"]


def test_categorical_distribution_shift_is_detected(monitoring_fixture):
    records = [dict(record, language="python") for record in monitoring_fixture["records"]]
    service, _ = _service(monitoring_fixture, records)

    report = service.get_report()

    drift = next(item for item in report["feature_drift"] if item["feature"] == "language")
    assert drift["status"] == "drift"
    assert drift["drift_score"] >= DRIFT_THRESHOLD


def test_prediction_distribution_shift_is_detected(monitoring_fixture):
    records = [dict(record, prediction="beginner") for record in monitoring_fixture["records"]]
    service, _ = _service(monitoring_fixture, records)

    report = service.get_report()

    assert report["prediction_drift"]["status"] == "drift"
    assert report["prediction_drift"]["drift_score"] >= DRIFT_THRESHOLD
    assert "prediction_distribution" in report["drifted_features"]


def test_drift_detector_uses_centralized_warning_and_drift_thresholds(monitoring_fixture):
    baseline = monitoring_fixture["baseline"]["numeric_features"]["assessment_accuracy"]
    result = compare_numeric_feature("assessment_accuracy", [10.0] * 150, baseline)

    assert result["warning_threshold"] == WARNING_THRESHOLD
    assert result["threshold"] == DRIFT_THRESHOLD
    categorical = compare_categorical_feature(
        "language",
        ["python"] * 150,
        monitoring_fixture["baseline"]["categorical_features"]["language"],
    )
    prediction = compare_prediction_distribution(
        ["beginner"] * 150,
        monitoring_fixture["baseline"]["prediction_distribution"],
    )
    assert categorical["status"] == "drift"
    assert prediction["status"] == "drift"


def test_insufficient_predictions_do_not_claim_stable_or_drift(monitoring_fixture):
    service, _ = _service(monitoring_fixture, monitoring_fixture["records"][:7], minimum=30)

    report = service.get_report()

    assert report["status"] == "insufficient_data"
    assert report["prediction_count"] == 7
    assert report["total_monitored_predictions"] == 7
    assert report["minimum_required"] == 30
    assert report["feature_drift"] == []
    assert report["prediction_drift"] is None


def test_report_tracks_versions_and_limits_window(monitoring_fixture):
    service, collection = _service(monitoring_fixture, monitoring_fixture["records"], window=40)

    report = service.get_report()

    assert report["model_version"] == "skill-model-v1"
    assert report["feature_version"] == "features-v1"
    assert report["baseline_version"] == "baseline-v1"
    assert report["dataset_version"] == monitoring_fixture["dataset_metadata"]["dataset_version"]
    assert report["prediction_count"] == 40
    assert collection.query == {"model_version": "skill-model-v1", "feature_version": "features-v1"}


def test_model_baseline_artifact_mismatch_is_not_reported_as_stable(monitoring_fixture):
    collection = FakePredictionCollection(monitoring_fixture["records"])
    mismatched_model = SimpleNamespace(
        ready=True,
        model_version="skill-model-v1",
        feature_version="features-v1",
        metadata={"training_sample_count": 999},
    )
    service = MonitoringService(
        baseline_path=monitoring_fixture["baseline_path"],
        prediction_collection_provider=lambda: collection,
        model_service_provider=lambda: mismatched_model,
        minimum_predictions=1,
    )

    report = service.get_report()

    assert report["status"] == "unavailable"
    assert report["reason"] == "baseline_model_artifact_mismatch"


def test_prediction_storage_unavailable_has_distinct_report_state(monitoring_fixture):
    service = MonitoringService(
        baseline_path=monitoring_fixture["baseline_path"],
        prediction_collection_provider=lambda: (_ for _ in ()).throw(RuntimeError("storage unavailable")),
        model_service_provider=lambda: _fake_model_service(monitoring_fixture["baseline"]),
    )

    report = service.get_report()

    assert report["status"] == "unavailable"
    assert report["reason"] == "prediction_storage_unavailable"
    assert report["total_monitored_predictions"] == 0


def test_prediction_logger_persists_required_fields_without_sensitive_data():
    collection = FakePredictionCollection()
    logger = PredictionLogger(lambda: collection)
    features = {
        **{name: (2 if name == "attempt_count" else 0.5) for name in NUMERIC_FEATURES},
        "language": "python",
        "topic": "Arrays",
        "student_id": "private-student",
        "password": "not-logged",
        "jwt": "not-logged",
        "source_code": "not-logged",
    }

    assert logger.log_prediction(
        features=features,
        prediction="intermediate",
        model_version="skill-model-v1",
        feature_version="features-v1",
    )
    document = collection.inserted[0]

    assert document["prediction_id"]
    assert document["timestamp"].tzinfo == timezone.utc
    assert document["model_version"] == "skill-model-v1"
    assert document["feature_version"] == "features-v1"
    assert document["language"] == "python"
    assert document["topic"] == "Arrays"
    assert document["prediction"] == "intermediate"
    assert set(document["features"]) == set(NUMERIC_FEATURES)
    assert not {"student_id", "password", "jwt", "source_code", "authorization"}.intersection(document)


def test_prediction_logger_failure_is_best_effort():
    logger = PredictionLogger(lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")))
    features = {
        **{name: (2 if name == "attempt_count" else 0.5) for name in NUMERIC_FEATURES},
        "language": "python",
        "topic": "Arrays",
    }

    assert not logger.log_prediction(
        features=features,
        prediction="intermediate",
        model_version="skill-model-v1",
        feature_version="features-v1",
    )


def test_prediction_collection_creates_useful_indexes(monkeypatch):
    collection = SimpleNamespace(indexes=[])
    collection.create_index = lambda keys, **kwargs: collection.indexes.append((keys, kwargs))
    database = {"ml_predictions": collection}
    monkeypatch.setattr(prediction_logger, "get_database", lambda: database)

    assert prediction_logger.get_prediction_collection() is collection
    assert collection.indexes == [
        ("prediction_id", {"unique": True}),
        ("timestamp", {}),
        ([
            ("model_version", 1),
            ("feature_version", 1),
            ("timestamp", -1),
        ], {}),
    ]


@pytest.fixture
def monitoring_client(monkeypatch, monitoring_fixture):
    records = monitoring_fixture["records"][:7]
    service, _ = _service(monitoring_fixture, records)
    user = {"user_id": "monitor-user"}
    collection = SimpleNamespace(find_one=lambda query: user if query.get("user_id") == user["user_id"] else None)
    monkeypatch.setattr(security, "get_database", lambda: SimpleNamespace(users=collection))
    monkeypatch.setattr(security.settings, "jwt_secret", "monitoring-test-jwt-secret-key-at-least-32-bytes")
    monkeypatch.setitem(app.dependency_overrides, get_monitoring_service, lambda: service)
    token = security.create_access_token(user["user_id"])
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


def test_monitoring_endpoints_require_authentication():
    client = TestClient(app)
    assert client.get("/ml/monitoring").status_code == 401
    assert client.get("/ml/monitoring/baseline").status_code == 401


def test_monitoring_endpoint_returns_aggregate_only(monitoring_client):
    response = monitoring_client.get("/ml/monitoring")

    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "insufficient_data"
    assert report["prediction_count"] == 7
    assert "prediction_id" not in response.text
    assert "student_id" not in response.text
    assert "features" not in report
    assert "prediction" not in report


def test_authenticated_baseline_endpoint_exposes_only_baseline_statistics(monitoring_client):
    response = monitoring_client.get("/ml/monitoring/baseline")

    assert response.status_code == 200
    baseline = response.json()
    assert baseline["baseline_version"] == "baseline-v1"
    assert baseline["sample_count"] == 150
    assert "numeric_features" in baseline
    assert "categorical_features" in baseline
    assert "prediction_id" not in response.text
