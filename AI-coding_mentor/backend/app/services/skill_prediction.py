from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import joblib

from app.models.language import ProgrammingLanguage
from app.services import assessment as assessment_service
from app.services import assessment_results as result_service
from ml.features.skill_features import build_feature_row, training_frame
from ml.models.skill_predictor import ARTIFACT_DIR


class SkillPredictionError(RuntimeError):
    pass


class ModelNotTrainedError(SkillPredictionError):
    pass


class InsufficientSkillDataError(SkillPredictionError):
    pass


def load_model(artifact_dir: Path | None = None):
    path = (artifact_dir or ARTIFACT_DIR) / "skill_model.joblib"
    if not path.exists():
        raise ModelNotTrainedError("Train the skill prediction model before requesting ML predictions.")
    try:
        return joblib.load(path)
    except Exception as error:
        raise SkillPredictionError("The skill prediction model artifact is invalid.") from error


def _latest_result(user_id: str) -> dict[str, Any] | None:
    return result_service.get_assessment_results_collection().find_one({"user_id": user_id}, sort=[("created_at", -1)])


def build_user_topic_features(*, user_id: str, language: ProgrammingLanguage) -> list[dict[str, Any]]:
    result = _latest_result(user_id)
    if result is None:
        raise InsufficientSkillDataError("Complete an assessment before requesting ML skill predictions.")
    submissions = list(assessment_service.get_assessment_submissions_collection().find({"user_id": user_id}))
    topics = result.get("topic_scores", {})
    rows = []
    for topic, assessment_accuracy in topics.items():
        topic_attempts = [item for item in submissions if item.get("question_topic") == topic]
        # Current submission records do not yet persist topic; assessment topic scores
        # remain the reliable per-topic signal until that field is added.
        solved = [item for item in topic_attempts if item.get("status") == "accepted"]
        rows.append(build_feature_row(
            language=language.value,
            topic=topic,
            assessment_accuracy=assessment_accuracy,
            easy_attempts=len(topic_attempts),
            easy_solved=len(solved),
            recent_attempts=len([item for item in topic_attempts if isinstance(item.get("submitted_at"), datetime) and item["submitted_at"] >= datetime.now(timezone.utc) - timedelta(days=30)]),
            recent_solved=len(solved),
            lesson_completion_rate=0.0,
        ))
    if not rows:
        raise InsufficientSkillDataError("No topic-level assessment data is available.")
    return rows


def predict_user_topics(*, user_id: str, language: ProgrammingLanguage, artifact_dir: Path | None = None) -> list[dict[str, Any]]:
    model = load_model(artifact_dir)
    rows = build_user_topic_features(user_id=user_id, language=language)
    frame = training_frame(rows)
    feature_frame = frame[["assessment_accuracy", "easy_success_rate", "medium_success_rate", "hard_success_rate", "overall_success_rate", "failure_rate", "recent_success_rate", "lesson_completion_rate", "attempt_count", "language", "topic"]]
    predictions = model.predict(feature_frame)
    probabilities = model.predict_proba(feature_frame) if hasattr(model, "predict_proba") else None
    classes = list(model.classes_) if probabilities is not None else []
    return [
        {
            "topic": row["topic"],
            "predicted_skill": str(predictions[index]),
            "confidence": float(max(probabilities[index])) if probabilities is not None else None,
            "rule_based_skill": "beginner" if row["assessment_accuracy"] < 0.4 else "intermediate" if row["assessment_accuracy"] < 0.7 else "advanced",
            "status": "predicted",
        }
        for index, row in enumerate(rows)
    ]
