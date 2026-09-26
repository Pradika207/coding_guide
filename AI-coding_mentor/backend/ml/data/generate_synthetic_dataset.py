"""Create reproducible, explicitly synthetic student-topic training data."""

import csv
import random
from pathlib import Path

from app.models.language import ProgrammingLanguage
from app.models.question import Topic

RANDOM_STATE = 42
TRAINING_SOURCE = "synthetic_development_data"
RAW_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "skill_training_data.csv"
COLUMNS = [
    "student_id",
    "language",
    "topic",
    "assessment_accuracy",
    "easy_success_rate",
    "medium_success_rate",
    "hard_success_rate",
    "overall_success_rate",
    "failure_rate",
    "recent_success_rate",
    "lesson_completion_rate",
    "attempt_count",
    "topic_count",
    "skill_level",
    "training_source",
]


def generate_rows(*, random_state: int = RANDOM_STATE, samples_per_class: int = 50) -> list[dict[str, object]]:
    rng = random.Random(random_state)
    languages = list(ProgrammingLanguage)
    topics = list(Topic)
    class_ranges = {
        "beginner": (10, 39, (0.15, 0.55)),
        "intermediate": (40, 69, (0.40, 0.80)),
        "advanced": (70, 99, (0.65, 1.0)),
    }
    rows: list[dict[str, object]] = []
    for skill_level, (accuracy_min, accuracy_max, success_range) in class_ranges.items():
        for class_index in range(samples_per_class):
            accuracy = rng.randint(accuracy_min, accuracy_max)
            easy_rate = rng.uniform(*success_range)
            medium_rate = max(0.0, min(1.0, easy_rate - rng.uniform(0.05, 0.35)))
            hard_rate = max(0.0, min(1.0, medium_rate - rng.uniform(0.05, 0.35)))
            attempts = [rng.randint(2, 10), rng.randint(0, 8), rng.randint(0, 6)]
            rates = [easy_rate, medium_rate, hard_rate]
            solved = [round(rate * count) for rate, count in zip(rates, attempts)]
            total_attempts = sum(attempts)
            total_solved = sum(solved)
            rows.append({
                "student_id": f"synthetic-{skill_level}-{class_index:03d}",
                "language": languages[(class_index + len(rows)) % len(languages)].value,
                "topic": topics[(class_index + len(rows)) % len(topics)].display_name,
                "assessment_accuracy": accuracy,
                "easy_success_rate": round(easy_rate, 6),
                "medium_success_rate": round(medium_rate, 6),
                "hard_success_rate": round(hard_rate, 6),
                "overall_success_rate": round(total_solved / total_attempts if total_attempts else 0.0, 6),
                "failure_rate": round((total_attempts - total_solved) / total_attempts if total_attempts else 0.0, 6),
                "recent_success_rate": round(rng.uniform(max(0.0, easy_rate - 0.25), min(1.0, easy_rate + 0.15)), 6),
                "lesson_completion_rate": round(rng.random(), 6),
                "attempt_count": total_attempts,
                "topic_count": rng.randint(1, 5),
                "skill_level": skill_level,
                "training_source": TRAINING_SOURCE,
            })
    return rows


def generate_dataset(output_path: Path = RAW_DATA_PATH, *, random_state: int = RANDOM_STATE) -> int:
    rows = generate_rows(random_state=random_state)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    count = generate_dataset()
    print(f"Generated {count} deterministic synthetic development rows: {RAW_DATA_PATH}")
