from pathlib import Path

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import skill_prediction
from app.services.security import get_current_user
from ml.features.skill_features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, build_feature_row, safe_divide, training_frame
from ml.models.skill_predictor import train_skill_model
from ml.training.skill_dataset import synthetic_training_rows


def test_safe_division_and_feature_values_are_finite():
    assert safe_divide(1, 0) == 0
    row = build_feature_row(language="java", topic="Arrays", assessment_accuracy=80)
    values = [row[key] for key in NUMERIC_FEATURES]
    assert all(np.isfinite(values))


def test_synthetic_dataset_contains_all_classes_and_no_identity_feature():
    rows = synthetic_training_rows()
    assert {row["target_skill"] for row in rows} == {"beginner", "intermediate", "advanced"}
    assert "student_id" in rows[0]
    frame = training_frame(rows)
    assert "student_id" not in NUMERIC_FEATURES + CATEGORICAL_FEATURES


def test_training_creates_model_and_metadata(tmp_path):
    result = train_skill_model(artifact_dir=tmp_path, enable_tracking=False)
    assert (tmp_path / "skill_model.joblib").exists()
    assert (tmp_path / "skill_metadata.json").exists()
    assert result["metadata"]["training_source"] == "synthetic_development_data"
    assert result["metadata"]["model_version"] == "skill-model-v1"
    loaded = joblib.load(tmp_path / "skill_model.joblib")
    prediction = loaded.predict(training_frame(synthetic_training_rows()).drop(columns=["target_skill", "student_id"]))
    assert set(prediction) == {"beginner", "intermediate", "advanced"}


def test_training_is_deterministic_for_predictions(tmp_path):
    first = train_skill_model(artifact_dir=tmp_path / "one", enable_tracking=False)
    second = train_skill_model(artifact_dir=tmp_path / "two", enable_tracking=False)
    rows = synthetic_training_rows()[:3]
    frame = training_frame(rows).drop(columns=["target_skill", "student_id"])
    assert first["model"].predict(frame).tolist() == second["model"].predict(frame).tolist()


def test_missing_model_is_explicit(tmp_path):
    with pytest.raises(skill_prediction.ModelNotTrainedError):
        skill_prediction.load_model(tmp_path)


def test_prediction_format_with_probabilities(tmp_path, monkeypatch):
    train_skill_model(artifact_dir=tmp_path)
    monkeypatch.setattr(skill_prediction, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(skill_prediction, "_latest_result", lambda _: {"topic_scores": {"Arrays": 60}})
    monkeypatch.setattr(skill_prediction.assessment_service, "get_assessment_submissions_collection", lambda: type("C", (), {"find": lambda self, _: []})())
    predictions = skill_prediction.predict_user_topics(user_id="user-1", language=__import__("app.models.language", fromlist=["ProgrammingLanguage"]).ProgrammingLanguage.JAVA)
    assert predictions[0]["topic"] == "Arrays"
    assert predictions[0]["predicted_skill"] in {"beginner", "intermediate", "advanced"}
    assert 0 <= predictions[0]["confidence"] <= 1
    assert predictions[0]["rule_based_skill"] == "intermediate"


def test_insufficient_data_is_explicit(monkeypatch):
    monkeypatch.setattr(skill_prediction, "_latest_result", lambda _: None)
    with pytest.raises(skill_prediction.InsufficientSkillDataError):
        skill_prediction.build_user_topic_features(user_id="user-1", language=__import__("app.models.language", fromlist=["ProgrammingLanguage"]).ProgrammingLanguage.JAVA)


def test_ml_endpoint_requires_authentication():
    assert TestClient(app).get("/ml/skill-profile").status_code == 401


def test_ml_endpoint_returns_model_state(monkeypatch):
    from app.models.language import ProgrammingLanguage
    monkeypatch.setattr(skill_prediction, "predict_user_topics", lambda **_: [])
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "selected_language": "java"}
    try:
        response = TestClient(app).get("/ml/skill-profile")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
