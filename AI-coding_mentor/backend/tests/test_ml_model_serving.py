import json
from pathlib import Path
from types import SimpleNamespace

import joblib
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import skill_ml
from app.services import security
from app.services.security import get_current_user
from ml.features.skill_features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_feature_row_from_rates,
    training_frame,
)
from ml.models.skill_predictor import train_skill_model
from ml.serving import skill_model_service as serving
from ml.training.skill_dataset import synthetic_training_rows


def _request_payload() -> dict[str, object]:
    return {
        "language": "python",
        "topic": "arrays",
        "assessment_accuracy": 74.0,
        "easy_success_rate": 0.8,
        "medium_success_rate": 0.5,
        "hard_success_rate": 0.25,
        "overall_success_rate": 0.6,
        "failure_rate": 0.4,
        "recent_success_rate": 0.7,
        "lesson_completion_rate": 0.65,
        "attempt_count": 12,
        "topic_count": 3,
    }


@pytest.fixture(scope="module")
def model_bundle(tmp_path_factory):
    artifact_dir = tmp_path_factory.mktemp("skill-serving-model")
    trained = train_skill_model(
        rows=synthetic_training_rows(),
        source="synthetic_development_data",
        artifact_dir=artifact_dir,
        enable_tracking=False,
    )
    service = serving.SkillModelService(
        model_path=trained["model_path"],
        metadata_path=trained["metadata_path"],
    )
    return {"trained": trained, "service": service}


@pytest.fixture
def model_service_override(monkeypatch, model_bundle):
    monkeypatch.setitem(
        app.dependency_overrides,
        serving.get_skill_model_service,
        lambda: model_bundle["service"],
    )
    return model_bundle["service"]


@pytest.fixture
def authenticated_client(monkeypatch, model_service_override):
    fake_user = {"user_id": "serving-test-user", "selected_language": "python"}
    fake_users = SimpleNamespace(find_one=lambda query: fake_user if query.get("user_id") == fake_user["user_id"] else None)
    monkeypatch.setattr(security, "get_database", lambda: SimpleNamespace(users=fake_users))
    monkeypatch.setattr(security.settings, "jwt_secret", "serving-tests-only-secret-key-32-bytes")
    monkeypatch.setattr(skill_ml, "log_prediction", lambda **_: True)
    token = security.create_access_token(fake_user["user_id"])
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


def test_model_loads_once_and_reuses_project_relative_singleton(monkeypatch, model_bundle):
    monkeypatch.setattr(serving, "_service_instance", None)
    monkeypatch.setattr(serving, "MODEL_PATH", model_bundle["trained"]["model_path"])
    monkeypatch.setattr(serving, "METADATA_PATH", model_bundle["trained"]["metadata_path"])
    original_load = joblib.load
    load_calls = []

    def count_load(path):
        load_calls.append(Path(path))
        return original_load(path)

    monkeypatch.setattr(serving.joblib, "load", count_load)
    first = serving.get_skill_model_service()
    second = serving.get_skill_model_service()

    assert first is second
    assert first.ready
    assert len(load_calls) == 1
    assert load_calls[0] == model_bundle["trained"]["model_path"]


def test_service_loads_metadata_versions_and_existing_feature_list(model_bundle):
    service = model_bundle["service"]
    metadata = service.metadata

    assert service.model_status == "ready"
    assert service.model_version == metadata["model_version"] == "skill-model-v1"
    assert service.feature_version == metadata["feature_version"] == "features-v1"
    assert metadata["feature_names"] == NUMERIC_FEATURES + CATEGORICAL_FEATURES
    assert "topic_count" not in metadata["feature_names"]
    assert "student_id" not in metadata["feature_names"]


def test_valid_feature_input_produces_an_existing_skill_class(authenticated_client):
    response = authenticated_client.post("/ml/predict-skill", json=_request_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["prediction"] in {"beginner", "intermediate", "advanced"}
    assert body["model_version"] == "skill-model-v1"
    assert body["feature_version"] == "features-v1"
    assert body["model_status"] == "ready"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("assessment_accuracy", 100.1),
        ("easy_success_rate", -0.01),
        ("overall_success_rate", 1.01),
        ("assessment_accuracy", "NaN"),
        ("failure_rate", "Infinity"),
        ("attempt_count", -1),
        ("topic_count", -1),
    ],
)
def test_invalid_numeric_values_are_rejected(authenticated_client, field, value):
    payload = _request_payload()
    payload[field] = value

    response = authenticated_client.post(
        "/ml/predict-skill",
        content=json.dumps(payload, allow_nan=True),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422


def test_unsupported_language_and_topic_are_rejected(authenticated_client):
    for field, value in (("language", "rust"), ("topic", "made_up_topic")):
        payload = _request_payload()
        payload[field] = value
        response = authenticated_client.post("/ml/predict-skill", json=payload)
        assert response.status_code == 422


def test_prediction_endpoint_requires_authentication():
    response = TestClient(app).post("/ml/predict-skill", json=_request_payload())

    assert response.status_code == 401


def test_authenticated_prediction_succeeds_through_existing_jwt_dependency(authenticated_client):
    response = authenticated_client.post("/ml/predict-skill", json=_request_payload())

    assert response.status_code == 200


def test_successful_prediction_logs_exact_features_and_versions(authenticated_client, monkeypatch):
    from app.routes import skill_ml

    logged = {}
    monkeypatch.setattr(skill_ml, "log_prediction", lambda **values: logged.update(values) or True)
    response = authenticated_client.post("/ml/predict-skill", json=_request_payload())

    assert response.status_code == 200
    assert logged["prediction"] == response.json()["prediction"]
    assert logged["model_version"] == "skill-model-v1"
    assert logged["feature_version"] == "features-v1"
    assert logged["features"]["assessment_accuracy"] == pytest.approx(0.74)
    assert logged["features"]["language"] == "python"
    assert logged["features"]["topic"] == "Arrays"
    assert "student_id" not in logged["features"]


def test_ml_health_reports_readiness_without_authentication(model_service_override):
    response = TestClient(app).get("/ml/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "model_status": "ready",
        "model_version": "skill-model-v1",
        "feature_version": "features-v1",
    }


def test_missing_model_returns_clean_health_and_prediction_errors(monkeypatch, tmp_path):
    missing_service = serving.SkillModelService(
        model_path=tmp_path / "absent.joblib",
        metadata_path=tmp_path / "absent.json",
    )
    monkeypatch.setitem(app.dependency_overrides, serving.get_skill_model_service, lambda: missing_service)
    health = TestClient(app).get("/ml/health")

    assert health.status_code == 503
    assert health.json()["model_status"] == "unavailable"
    assert str(tmp_path) not in health.text

    fake_user = {"user_id": "serving-test-user"}
    monkeypatch.setattr(security, "get_database", lambda: SimpleNamespace(
        users=SimpleNamespace(find_one=lambda query: fake_user if query.get("user_id") == fake_user["user_id"] else None)
    ))
    monkeypatch.setattr(security.settings, "jwt_secret", "serving-tests-only-secret-key-32-bytes")
    token = security.create_access_token(fake_user["user_id"])
    response = TestClient(app).post(
        "/ml/predict-skill",
        json=_request_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Skill prediction model is unavailable"
    assert str(tmp_path) not in response.text


def test_prediction_failure_is_sanitized(monkeypatch, model_bundle):
    class FailingModel:
        def predict(self, _features):
            raise RuntimeError("private estimator detail")

    failing_service = model_bundle["service"]
    failing_service._model = FailingModel()
    monkeypatch.setitem(app.dependency_overrides, serving.get_skill_model_service, lambda: failing_service)
    fake_user = {"user_id": "serving-test-user"}
    fake_users = SimpleNamespace(find_one=lambda query: fake_user if query.get("user_id") == fake_user["user_id"] else None)
    monkeypatch.setattr(security, "get_database", lambda: SimpleNamespace(users=fake_users))
    monkeypatch.setattr(security.settings, "jwt_secret", "serving-tests-only-secret-key-32-bytes")
    token = security.create_access_token(fake_user["user_id"])

    try:
        response = TestClient(app).post(
            "/ml/predict-skill",
            json=_request_payload(),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 500
        assert response.json()["detail"] == "Skill prediction failed"
        assert "private estimator detail" not in response.text
    finally:
        failing_service._model = model_bundle["trained"]["model"]


def test_student_id_is_rejected_and_never_becomes_a_model_feature(authenticated_client):
    payload = _request_payload()
    payload["student_id"] = "not-a-feature"

    response = authenticated_client.post("/ml/predict-skill", json=payload)

    assert response.status_code == 422
    assert "student_id" not in NUMERIC_FEATURES + CATEGORICAL_FEATURES


def test_serving_prediction_matches_direct_model_prediction(authenticated_client, model_bundle):
    payload = _request_payload()
    feature_row = build_feature_row_from_rates(
        language=payload["language"],
        topic="Arrays",
        assessment_accuracy=payload["assessment_accuracy"],
        easy_success_rate=payload["easy_success_rate"],
        medium_success_rate=payload["medium_success_rate"],
        hard_success_rate=payload["hard_success_rate"],
        overall_success_rate=payload["overall_success_rate"],
        failure_rate=payload["failure_rate"],
        recent_success_rate=payload["recent_success_rate"],
        lesson_completion_rate=payload["lesson_completion_rate"],
        attempt_count=payload["attempt_count"],
    )
    direct_features = training_frame([feature_row])[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    direct_prediction = str(model_bundle["trained"]["model"].predict(direct_features)[0])
    response = authenticated_client.post("/ml/predict-skill", json=payload)

    assert response.status_code == 200
    assert response.json()["prediction"] == direct_prediction