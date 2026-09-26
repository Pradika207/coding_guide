from math import isfinite
from typing import Any

NUMERIC_FEATURES = [
    "assessment_accuracy",
    "easy_success_rate",
    "medium_success_rate",
    "hard_success_rate",
    "overall_success_rate",
    "failure_rate",
    "recent_success_rate",
    "lesson_completion_rate",
    "attempt_count",
]
CATEGORICAL_FEATURES = ["language", "topic"]
FEATURE_VERSION = "features-v1"


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    value = numerator / denominator
    return value if isfinite(value) else 0.0


def _normalize_assessment_accuracy(value: float) -> float:
    return max(0.0, min(float(value), 100.0)) / 100


def _normalize_lesson_completion_rate(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def build_feature_row_from_rates(
    *,
    language: str,
    topic: str,
    assessment_accuracy: float,
    easy_success_rate: float,
    medium_success_rate: float,
    hard_success_rate: float,
    overall_success_rate: float,
    failure_rate: float,
    recent_success_rate: float,
    lesson_completion_rate: float,
    attempt_count: int,
) -> dict[str, Any]:
    """Build the model's existing feature shape from already-computed rates."""
    return {
        "language": language,
        "topic": topic,
        "assessment_accuracy": _normalize_assessment_accuracy(assessment_accuracy),
        "easy_success_rate": float(easy_success_rate),
        "medium_success_rate": float(medium_success_rate),
        "hard_success_rate": float(hard_success_rate),
        "overall_success_rate": float(overall_success_rate),
        "failure_rate": float(failure_rate),
        "recent_success_rate": float(recent_success_rate),
        "lesson_completion_rate": _normalize_lesson_completion_rate(lesson_completion_rate),
        "attempt_count": int(attempt_count),
    }


def build_feature_row(*, language: str, topic: str, assessment_accuracy: float = 0.0, easy_attempts: int = 0, easy_solved: int = 0, medium_attempts: int = 0, medium_solved: int = 0, hard_attempts: int = 0, hard_solved: int = 0, recent_attempts: int = 0, recent_solved: int = 0, lesson_completion_rate: float = 0.0, target_skill: str | None = None, student_id: str | None = None) -> dict[str, Any]:
    total_attempts = easy_attempts + medium_attempts + hard_attempts
    total_solved = easy_solved + medium_solved + hard_solved
    row: dict[str, Any] = {
        "language": language,
        "topic": topic,
        "assessment_accuracy": _normalize_assessment_accuracy(assessment_accuracy),
        "easy_success_rate": safe_divide(easy_solved, easy_attempts),
        "medium_success_rate": safe_divide(medium_solved, medium_attempts),
        "hard_success_rate": safe_divide(hard_solved, hard_attempts),
        "overall_success_rate": safe_divide(total_solved, total_attempts),
        "failure_rate": safe_divide(total_attempts - total_solved, total_attempts),
        "recent_success_rate": safe_divide(recent_solved, recent_attempts),
        "lesson_completion_rate": _normalize_lesson_completion_rate(lesson_completion_rate),
        "attempt_count": total_attempts,
    }
    if target_skill is not None:
        row["target_skill"] = target_skill
    if student_id is not None:
        row["student_id"] = student_id
    return row


def training_frame(rows: list[dict[str, Any]]):
    import pandas as pd
    return pd.DataFrame(rows)
