from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ml.features.skill_features import CATEGORICAL_FEATURES, FEATURE_VERSION, NUMERIC_FEATURES, training_frame
from ml.training.skill_dataset import load_training_rows

MODEL_VERSION = "skill-model-v1"
ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "skill_model.joblib"
METADATA_PATH = ARTIFACT_DIR / "skill_metadata.json"


def build_pipeline() -> Pipeline:
    preprocess = ColumnTransformer([
        ("numeric", "passthrough", NUMERIC_FEATURES),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    return Pipeline([
        ("preprocess", preprocess),
        ("classifier", RandomForestClassifier(n_estimators=120, random_state=42, class_weight="balanced")),
    ])


def train_skill_model(*, rows: list[dict[str, Any]] | None = None, source: str | None = None, artifact_dir: Path | None = None, enable_tracking: bool = True) -> dict[str, Any]:
    configured_data_path = os.getenv("SKILL_TRAINING_DATA_PATH", "").strip()
    using_configured_dataset = rows is None and bool(configured_data_path)
    if rows is None:
        rows, source = load_training_rows()
    source = source or "unknown"
    frame = training_frame(rows)
    if len(frame) < 12 or frame["target_skill"].nunique() < 3:
        raise ValueError("At least 12 samples across all three skill classes are required")
    x = frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = frame["target_skill"]
    x_train, x_valid, y_train, y_valid = train_test_split(x, y, test_size=0.2, random_state=42, stratify=y)
    model = build_pipeline()
    model.fit(x_train, y_train)
    predictions = model.predict(x_valid)
    labels = sorted(y.unique().tolist())
    metrics = {
        "accuracy": accuracy_score(y_valid, predictions),
        "precision": precision_score(y_valid, predictions, average="weighted", zero_division=0),
        "recall": recall_score(y_valid, predictions, average="weighted", zero_division=0),
        "f1": f1_score(y_valid, predictions, average="weighted", zero_division=0),
        "classification_report": classification_report(y_valid, predictions, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_valid, predictions, labels=labels).tolist(),
        "training_sample_count": len(x_train),
        "validation_sample_count": len(x_valid),
    }
    destination = artifact_dir or ARTIFACT_DIR
    destination.mkdir(parents=True, exist_ok=True)
    model_path = destination / "skill_model.joblib"
    metadata_path = destination / "skill_metadata.json"
    joblib.dump(model, model_path)
    metadata = {
        "model_name": "RandomForestClassifier",
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "feature_names": NUMERIC_FEATURES + CATEGORICAL_FEATURES,
        "training_source": source,
        "training_sample_count": len(frame),
        "training_split_count": len(x_train),
        "validation_sample_count": len(x_valid),
        "class_labels": labels,
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "training_data_note": "Labels are derived from historical rule-based score thresholds; they are not ground-truth skill labels.",
    }
    if using_configured_dataset:
        dataset_path = Path(configured_data_path).expanduser()
        if not dataset_path.is_absolute():
            dataset_path = Path.cwd() / dataset_path
        dataset_metadata_path = dataset_path.parent / "dataset_metadata.json"
        dataset_metadata = {}
        if dataset_metadata_path.exists():
            dataset_metadata = json.loads(dataset_metadata_path.read_text(encoding="utf-8"))
        metadata.update({
            "dataset_version": dataset_metadata.get("dataset_version", "unknown"),
            "dataset_path": str(dataset_path.resolve()),
            "sample_count": len(frame),
            "feature_count": len(NUMERIC_FEATURES + CATEGORICAL_FEATURES),
        })
    classifier = model.named_steps["classifier"]
    tracking_params = {
        "random_state": 42,
        "test_size": 0.2,
        "n_estimators": classifier.n_estimators,
        "max_depth": classifier.max_depth,
        "min_samples_split": classifier.min_samples_split,
        "min_samples_leaf": classifier.min_samples_leaf,
        "average": "weighted",
    }
    if enable_tracking:
        from ml.tracking.mlflow_tracker import track_training_run

        tracking = track_training_run(
            model=model,
            metadata=metadata,
            params=tracking_params,
            metrics={
                "accuracy": metrics["accuracy"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1_score": metrics["f1"],
                "f1": metrics["f1"],
                "training_sample_count": len(x_train),
                "validation_sample_count": len(x_valid),
            },
        )
    else:
        tracking = {"status": "disabled", "reason": "Tracking disabled by caller"}
    metadata["mlflow"] = tracking
    if tracking.get("status") == "tracked":
        metadata["mlflow_experiment"] = tracking.get("experiment_name")
        metadata["mlflow_run_id"] = tracking.get("run_id")
    metadata_path.write_text(__import__("json").dumps(metadata, indent=2), encoding="utf-8")
    return {"model": model, "metadata": metadata, "model_path": model_path, "metadata_path": metadata_path, "tracking": tracking}
