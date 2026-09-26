"""Validate and normalize raw skill training data for model training."""

import csv
import json
import math
from pathlib import Path
from typing import Any

from app.models.language import ProgrammingLanguage
from app.models.question import Topic
from ml.data.generate_synthetic_dataset import TRAINING_SOURCE
from ml.features.skill_features import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from ml.training.skill_dataset import CLASS_LABELS

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
RAW_DATA_PATH = DATA_ROOT / "raw" / "skill_training_data.csv"
PROCESSED_DATA_PATH = DATA_ROOT / "processed" / "skill_training_data_processed.csv"
METADATA_PATH = DATA_ROOT / "processed" / "dataset_metadata.json"
RANDOM_STATE = 42
DATASET_VERSION = "dataset-v1"
REQUIRED_COLUMNS = {
    "student_id", "language", "topic", "assessment_accuracy",
    "easy_success_rate", "medium_success_rate", "hard_success_rate",
    "overall_success_rate", "failure_rate", "recent_success_rate",
    "lesson_completion_rate", "attempt_count", "topic_count", "skill_level",
}


def _number(value: Any, *, default: float = 0.0) -> float:
    if value is None or str(value).strip() == "":
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _normalize_topic(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    try:
        return Topic(normalized).display_name
    except ValueError:
        return normalized.replace("_", " ").title()


def _normalize_language(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("+", "p")
    try:
        return ProgrammingLanguage(normalized).value
    except ValueError:
        return normalized


def prepare_dataset(raw_path: Path = RAW_DATA_PATH, processed_path: Path = PROCESSED_DATA_PATH, metadata_path: Path = METADATA_PATH) -> dict[str, Any]:
    with raw_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Raw training data is missing required columns: {sorted(missing)}")
        raw_rows = list(reader)

    processed: list[dict[str, Any]] = []
    for row in raw_rows:
        skill = (row.get("skill_level") or "").strip().lower()
        if skill not in CLASS_LABELS:
            raise ValueError(f"Unsupported skill_level label: {skill!r}")
        language = _normalize_language(row.get("language") or "python")
        topic = _normalize_topic(row.get("topic") or "fundamentals")
        accuracy = _number(row.get("assessment_accuracy"))
        if accuracy > 1:
            accuracy /= 100.0
        normalized = {
            "student_id": (row.get("student_id") or "unknown").strip(),
            "language": language,
            "topic": topic,
            "assessment_accuracy": max(0.0, min(accuracy, 1.0)),
            "easy_success_rate": max(0.0, min(_number(row.get("easy_success_rate")), 1.0)),
            "medium_success_rate": max(0.0, min(_number(row.get("medium_success_rate")), 1.0)),
            "hard_success_rate": max(0.0, min(_number(row.get("hard_success_rate")), 1.0)),
            "overall_success_rate": max(0.0, min(_number(row.get("overall_success_rate")), 1.0)),
            "failure_rate": max(0.0, min(_number(row.get("failure_rate")), 1.0)),
            "recent_success_rate": max(0.0, min(_number(row.get("recent_success_rate")), 1.0)),
            "lesson_completion_rate": max(0.0, min(_number(row.get("lesson_completion_rate")), 1.0)),
            "attempt_count": max(0, int(_number(row.get("attempt_count")))),
            "topic_count": max(0, int(_number(row.get("topic_count")))),
            "skill_level": skill,
            "training_source": (row.get("training_source") or "unspecified").strip() or "unspecified",
        }
        processed.append(normalized)

    processed_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep a fixed explicit order for reproducible output bytes. student_id is
    # retained for provenance, but is intentionally not a model feature.
    columns_out = [
        "student_id", "language", "topic", "assessment_accuracy",
        "easy_success_rate", "medium_success_rate", "hard_success_rate",
        "overall_success_rate", "failure_rate", "recent_success_rate",
        "lesson_completion_rate", "attempt_count", "topic_count", "skill_level", "training_source",
    ]
    with processed_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns_out, lineterminator="\n")
        writer.writeheader()
        writer.writerows(processed)

    sources = sorted({row["training_source"] for row in processed})
    feature_columns = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    metadata = {
        "dataset_version": DATASET_VERSION,
        "training_source": sources[0] if len(sources) == 1 else "mixed",
        "row_count": len(processed),
        "column_count": len(columns_out),
        "feature_columns": feature_columns,
        "target_column": "skill_level",
        "random_state": RANDOM_STATE,
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


if __name__ == "__main__":
    metadata = prepare_dataset()
    print(json.dumps(metadata, indent=2))
