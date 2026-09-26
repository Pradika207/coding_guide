import csv
import json
import pytest

from ml.data.generate_synthetic_dataset import COLUMNS, TRAINING_SOURCE, generate_dataset
from ml.data.prepare_skill_dataset import DATASET_VERSION, prepare_dataset
from ml.features.skill_features import NUMERIC_FEATURES, CATEGORICAL_FEATURES
from ml.models.skill_predictor import train_skill_model
from ml.training.skill_dataset import CLASS_LABELS, load_training_rows


def test_synthetic_generation_is_deterministic_and_schema_is_valid(tmp_path):
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    assert generate_dataset(first_path, random_state=42) == 150
    generate_dataset(second_path, random_state=42)

    assert first_path.read_bytes() == second_path.read_bytes()
    with first_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
    assert set(COLUMNS).issubset(reader.fieldnames or [])
    assert {row["skill_level"] for row in rows} == set(CLASS_LABELS)
    assert {row["training_source"] for row in rows} == {TRAINING_SOURCE}


def test_preparation_writes_processed_data_and_metadata(tmp_path):
    raw_path = tmp_path / "raw.csv"
    processed_path = tmp_path / "processed" / "data.csv"
    metadata_path = tmp_path / "processed" / "dataset_metadata.json"
    generate_dataset(raw_path)

    metadata = prepare_dataset(raw_path, processed_path, metadata_path)

    assert processed_path.exists()
    assert metadata_path.exists()
    assert metadata["dataset_version"] == DATASET_VERSION == "dataset-v1"
    assert metadata["training_source"] == "synthetic_development_data"
    assert metadata["row_count"] == 150
    assert metadata["feature_columns"] == NUMERIC_FEATURES + CATEGORICAL_FEATURES
    assert "student_id" not in metadata["feature_columns"]
    assert metadata["target_column"] == "skill_level"
    assert metadata["random_state"] == 42
    assert json.loads(metadata_path.read_text(encoding="utf-8")) == metadata


def test_missing_values_are_handled_deterministically(tmp_path):
    raw_path = tmp_path / "raw.csv"
    generate_dataset(raw_path)
    with raw_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames
        rows = list(reader)
    rows[0]["language"] = ""
    rows[0]["topic"] = ""
    rows[0]["assessment_accuracy"] = ""
    rows[0]["attempt_count"] = ""
    with raw_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    processed_path = tmp_path / "processed.csv"
    metadata_path = tmp_path / "metadata.json"
    prepare_dataset(raw_path, processed_path, metadata_path)
    first = processed_path.read_bytes()
    prepare_dataset(raw_path, processed_path, metadata_path)

    assert processed_path.read_bytes() == first
    with processed_path.open(newline="", encoding="utf-8") as source:
        row = next(csv.DictReader(source))
    assert row["language"] == "python"
    assert row["topic"] == "Fundamentals"
    assert row["assessment_accuracy"] == "0.0"
    assert row["attempt_count"] == "0"


def test_invalid_skill_level_is_rejected(tmp_path):
    raw_path = tmp_path / "raw.csv"
    generate_dataset(raw_path)
    content = raw_path.read_text(encoding="utf-8").replace(",beginner,synthetic_development_data", ",expert,synthetic_development_data", 1)
    raw_path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported skill_level"):
        prepare_dataset(raw_path, tmp_path / "processed.csv", tmp_path / "metadata.json")


def test_default_training_falls_back_to_synthetic_rows(monkeypatch):
    monkeypatch.delenv("SKILL_TRAINING_DATA_PATH", raising=False)
    rows, source = load_training_rows()
    assert len(rows) == 30
    assert source == "synthetic_development_data"


def test_training_consumes_configured_processed_dataset(tmp_path, monkeypatch):
    raw_path = tmp_path / "raw.csv"
    processed_path = tmp_path / "processed" / "skill_training_data_processed.csv"
    metadata_path = tmp_path / "processed" / "dataset_metadata.json"
    generate_dataset(raw_path)
    prepare_dataset(raw_path, processed_path, metadata_path)
    monkeypatch.setenv("SKILL_TRAINING_DATA_PATH", str(processed_path))

    rows, source = load_training_rows()
    trained = train_skill_model(artifact_dir=tmp_path / "artifacts", enable_tracking=False)

    assert len(rows) == 150
    assert source == "synthetic_development_data"
    assert trained["metadata"]["training_source"] == "synthetic_development_data"
    assert trained["metadata"]["dataset_version"] == "dataset-v1"
    assert trained["metadata"]["dataset_path"] == str(processed_path.resolve())
    assert trained["metadata"]["sample_count"] == 150
    assert trained["metadata"]["feature_count"] == len(NUMERIC_FEATURES + CATEGORICAL_FEATURES)
    assert trained["metadata"]["mlflow"]["status"] == "disabled"


def test_training_passes_dataset_context_to_optional_mlflow(tmp_path, monkeypatch):
    from ml.models import skill_predictor

    raw_path = tmp_path / "raw.csv"
    processed_path = tmp_path / "processed" / "data.csv"
    generate_dataset(raw_path)
    prepare_dataset(raw_path, processed_path, processed_path.parent / "dataset_metadata.json")
    monkeypatch.setenv("SKILL_TRAINING_DATA_PATH", str(processed_path))
    captured = {}

    def capture_tracking_run(**kwargs):
        captured.update(kwargs)
        return {"status": "tracked", "run_id": "test-run"}

    monkeypatch.setattr("ml.tracking.mlflow_tracker.track_training_run", capture_tracking_run)
    result = train_skill_model(artifact_dir=tmp_path / "artifacts", enable_tracking=True)

    assert result["tracking"]["status"] == "tracked"
    assert captured["metadata"]["training_source"] == "synthetic_development_data"
    assert captured["metadata"]["dataset_version"] == "dataset-v1"
    assert captured["metadata"]["dataset_path"] == str(processed_path.resolve())
    assert captured["metadata"]["sample_count"] == 150
    assert captured["metadata"]["feature_count"] == len(NUMERIC_FEATURES + CATEGORICAL_FEATURES)
    assert {"accuracy", "precision", "recall", "f1", "f1_score"}.issubset(captured["metrics"])
    assert captured["params"]["random_state"] == 42
