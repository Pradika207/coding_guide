import csv
import json
import os
from pathlib import Path
from typing import Any

from ml.features.skill_features import NUMERIC_FEATURES, build_feature_row


CLASS_LABELS = ("beginner", "intermediate", "advanced")


def synthetic_training_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    profiles = [
        ("beginner", 20, 4, 1, 0, 0, 0, 0, 0.1),
        ("intermediate", 55, 5, 3, 4, 2, 1, 0, 0.5),
        ("advanced", 88, 8, 8, 7, 5, 3, 2, 0.9),
    ]
    for index in range(30):
        label, accuracy, easy_attempts, easy_solved, medium_attempts, medium_solved, hard_attempts, hard_solved, lessons = profiles[index % 3]
        rows.append(build_feature_row(
            student_id=f"synthetic-{index:03d}",
            language=("java", "python", "cpp")[index % 3],
            topic=("Arrays", "Loops", "Sorting", "Strings")[index % 4],
            assessment_accuracy=accuracy + (index % 3),
            easy_attempts=easy_attempts,
            easy_solved=easy_solved,
            medium_attempts=medium_attempts,
            medium_solved=medium_solved,
            hard_attempts=hard_attempts,
            hard_solved=hard_solved,
            recent_attempts=easy_attempts,
            recent_solved=easy_solved,
            lesson_completion_rate=lessons,
            target_skill=label,
        ))
    return rows


def load_real_training_rows() -> list[dict[str, Any]]:
    # Real-data extraction is intentionally isolated for later expansion. Current
    # stored assessment reports do not yet contain enough per-topic attempt detail.
    return []


def load_training_rows() -> tuple[list[dict[str, Any]], str]:
    configured_path = os.getenv("SKILL_TRAINING_DATA_PATH", "").strip()
    if configured_path:
        dataset_path = Path(configured_path).expanduser()
        if not dataset_path.is_absolute():
            dataset_path = Path.cwd() / dataset_path
        with dataset_path.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        for row in rows:
            row["target_skill"] = row.pop("skill_level", row.get("target_skill", ""))
            for feature in NUMERIC_FEATURES:
                value = row.get(feature, "")
                row[feature] = float(value) if value not in (None, "") else 0.0
        return rows, _training_source_for(dataset_path)

    real_rows = load_real_training_rows()
    if len(real_rows) >= 12 and len({row["target_skill"] for row in real_rows}) == 3:
        return real_rows, "real_rule_based_labels"
    return synthetic_training_rows(), "synthetic_development_data"


def _training_source_for(dataset_path: Path) -> str:
    metadata_path = dataset_path.parent / "dataset_metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return str(metadata.get("training_source") or "unknown")
    return "external_dataset"
