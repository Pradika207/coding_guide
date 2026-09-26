"""Candidate retraining orchestration with evaluation and guarded promotion."""

from __future__ import annotations

import csv
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

from app.database.config import settings
from app.models.language import ProgrammingLanguage
from app.models.question import Topic
from ml.features.skill_features import CATEGORICAL_FEATURES, FEATURE_VERSION, NUMERIC_FEATURES, training_frame
from ml.models.skill_predictor import ARTIFACT_DIR, MODEL_PATH, METADATA_PATH, build_pipeline
from ml.monitoring.baseline import DEFAULT_BASELINE_PATH, create_monitoring_baseline, load_monitoring_baseline
from ml.monitoring.monitoring_service import get_monitoring_service
from ml.retraining.artifact_promoter import ArtifactPromoter
from ml.retraining.promotion_gate import evaluate_promotion_gate
from ml.retraining.retraining_report import REPORT_PATH, build_retraining_report, write_retraining_report
from ml.retraining.retraining_trigger import determine_retraining_need
from ml.retraining.versions import next_baseline_version, next_model_version

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = BACKEND_ROOT / "data" / "processed" / "skill_training_data_processed.csv"
DEFAULT_CANDIDATE_DIR = ARTIFACT_DIR / "candidates"
REQUIRED_COLUMNS = set(NUMERIC_FEATURES + CATEGORICAL_FEATURES + ["skill_level"])
SUPPORTED_SKILLS = {"beginner", "intermediate", "advanced"}


class RetrainingDataError(ValueError):
    """Raised when a processed training dataset cannot be used safely."""


def load_and_validate_training_data(
    dataset_path: Path = DEFAULT_DATA_PATH,
    *,
    minimum_samples: int | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    minimum = minimum_samples or settings.minimum_retraining_samples
    if not dataset_path.is_file():
        raise RetrainingDataError(f"Processed training dataset is missing: {dataset_path.name}")
    metadata_path = dataset_path.parent / "dataset_metadata.json"
    if not metadata_path.is_file():
        raise RetrainingDataError("Processed dataset metadata is missing")
    with dataset_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        available_columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - available_columns
        if missing:
            raise RetrainingDataError(f"Processed dataset is missing required columns: {sorted(missing)}")
        rows = list(reader)
    if len(rows) < minimum:
        raise RetrainingDataError(f"At least {minimum} processed samples are required; found {len(rows)}")

    valid_languages = {language.value for language in ProgrammingLanguage}
    valid_topics = {topic.display_name for topic in Topic}
    clean_rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, start=2):
        try:
            cleaned: dict[str, Any] = {}
            for feature in NUMERIC_FEATURES:
                number = float(row[feature])
                if not math.isfinite(number):
                    raise ValueError(f"{feature} must be finite")
                if feature != "attempt_count" and not 0 <= number <= 1:
                    raise ValueError(f"{feature} must be between 0 and 1")
                if feature == "attempt_count" and (number < 0 or not number.is_integer()):
                    raise ValueError("attempt_count must be a non-negative integer")
                cleaned[feature] = int(number) if feature == "attempt_count" else number
            language = row["language"].strip().lower()
            topic = row["topic"].strip()
            if language not in valid_languages:
                raise ValueError(f"unsupported language {language!r}")
            if topic not in valid_topics:
                raise ValueError(f"unsupported topic {topic!r}")
            target = row["skill_level"].strip().lower()
            if target not in SUPPORTED_SKILLS:
                raise ValueError(f"unsupported skill_level {target!r}")
            cleaned.update({"language": language, "topic": topic, "target_skill": target})
            clean_rows.append(cleaned)
        except (KeyError, TypeError, ValueError) as error:
            raise RetrainingDataError(f"Invalid processed dataset row {row_number}: {error}") from error

    classes = {row["target_skill"] for row in clean_rows}
    if classes != SUPPORTED_SKILLS:
        raise RetrainingDataError("Processed dataset must contain beginner, intermediate, and advanced classes")
    try:
        dataset_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RetrainingDataError("Processed dataset metadata is invalid") from error
    if not isinstance(dataset_metadata, dict) or not dataset_metadata.get("dataset_version"):
        raise RetrainingDataError("Processed dataset metadata must provide dataset_version")
    declared_rows = dataset_metadata.get("row_count")
    if declared_rows is not None and declared_rows != len(clean_rows):
        raise RetrainingDataError("Processed dataset row count does not match its metadata")
    return training_frame(clean_rows), dataset_metadata


def evaluate_model(model: Any, x_valid: pd.DataFrame, y_valid: pd.Series) -> dict[str, Any]:
    predictions = model.predict(x_valid)
    labels = sorted(SUPPORTED_SKILLS)
    return {
        "accuracy": float(accuracy_score(y_valid, predictions)),
        "precision": float(precision_score(y_valid, predictions, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_valid, predictions, average="weighted", zero_division=0)),
        "f1": float(f1_score(y_valid, predictions, average="weighted", zero_division=0)),
        "validation_sample_count": int(len(y_valid)),
        "classification_report": classification_report(y_valid, predictions, labels=labels, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_valid, predictions, labels=labels).tolist(),
    }


def _write_candidate_metadata(metadata: dict[str, Any], path: Path) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class RetrainingService:
    def __init__(
        self,
        *,
        dataset_path: Path | None = None,
        model_path: Path = MODEL_PATH,
        metadata_path: Path = METADATA_PATH,
        baseline_path: Path = DEFAULT_BASELINE_PATH,
        candidate_dir: Path = DEFAULT_CANDIDATE_DIR,
        report_path: Path = REPORT_PATH,
        monitoring_service: Any | None = None,
        artifact_promoter: ArtifactPromoter | None = None,
        minimum_samples: int | None = None,
        minimum_new_rows: int | None = None,
        minimum_accuracy: float | None = None,
        minimum_f1: float | None = None,
    ) -> None:
        configured_data_path = os.getenv("SKILL_TRAINING_DATA_PATH", "").strip()
        selected_path = Path(configured_data_path).expanduser() if configured_data_path else DEFAULT_DATA_PATH
        if not selected_path.is_absolute():
            selected_path = Path.cwd() / selected_path
        self.dataset_path = dataset_path or selected_path
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.baseline_path = baseline_path
        self.candidate_dir = candidate_dir
        self.report_path = report_path
        self.monitoring_service = monitoring_service or get_monitoring_service()
        self.minimum_samples = minimum_samples or settings.minimum_retraining_samples
        self.minimum_new_rows = minimum_new_rows or settings.minimum_new_training_rows
        self.minimum_accuracy = minimum_accuracy
        self.minimum_f1 = minimum_f1
        self.artifact_promoter = artifact_promoter or ArtifactPromoter(
            model_path=model_path,
            metadata_path=metadata_path,
            baseline_path=baseline_path,
            backup_dir=model_path.parent / "backups",
        )

    def run(
        self,
        *,
        force: bool = False,
        monitoring_report: dict[str, Any] | None = None,
        enable_mlflow: bool = True,
    ) -> dict[str, Any]:
        old_version: str | None = None
        data_version: str | None = None
        training_source: str | None = None
        trigger = {"retrain_required": False, "reason": "unavailable", "drifted_features": []}
        candidate_version: str | None = None
        candidate_metrics: dict[str, Any] | None = None
        current_metrics: dict[str, Any] | None = None
        mlflow_result: dict[str, Any] = {"status": "not_attempted"}
        try:
            current_metadata = self._read_current_metadata()
            old_version = current_metadata["model_version"]
            candidate_version = next_model_version(old_version)
            dataset_frame, dataset_metadata = load_and_validate_training_data(
                self.dataset_path,
                minimum_samples=self.minimum_samples,
            )
            data_version = str(dataset_metadata["dataset_version"])
            training_source = str(dataset_metadata.get("training_source", "unknown"))
            if not self.model_path.is_file():
                raise RetrainingDataError("Current production model artifact is missing")
            current_model = joblib.load(self.model_path)
            if current_metadata.get("feature_version") != FEATURE_VERSION:
                raise RetrainingDataError("Current model feature version does not match the training pipeline")
            new_training_rows = max(0, len(dataset_frame) - int(current_metadata.get("training_sample_count", 0)))
            if force:
                monitoring_report = monitoring_report or {"status": "unavailable"}
            elif monitoring_report is None:
                monitoring_report = self.monitoring_service.get_report()
            trigger = determine_retraining_need(
                monitoring_report,
                new_training_rows=new_training_rows,
                minimum_new_rows=self.minimum_new_rows,
                force=force,
            )
            if not trigger["retrain_required"]:
                report = build_retraining_report(
                    status="not_required",
                    trigger=trigger["reason"],
                    old_model_version=old_version,
                    candidate_model_version=None,
                    dataset_version=data_version,
                    training_source=training_source,
                )
                return self._save_report(report)

            candidate_model, candidate_metadata, candidate_metrics, current_metrics = self._train_and_evaluate(
                dataset_frame=dataset_frame,
                dataset_metadata=dataset_metadata,
                current_metadata=current_metadata,
                current_model=current_model,
                candidate_version=candidate_version,
            )
            gate = evaluate_promotion_gate(
                candidate_metrics,
                current_metrics,
                minimum_accuracy=self.minimum_accuracy,
                minimum_f1=self.minimum_f1,
            )
            accepted = bool(gate["accepted"])
            rejection_reason = None if accepted else gate["reason"]
            candidate_metadata.update({
                "current_metrics": current_metrics,
                "candidate_metrics": candidate_metrics,
                "promotion_decision": "eligible" if accepted else "rejected",
                "rejection_reason": rejection_reason,
                "promotion_gate": gate,
                "trigger": trigger,
            })
            self.candidate_dir.mkdir(parents=True, exist_ok=True)
            candidate_model_path = self.candidate_dir / "skill_model_candidate.joblib"
            candidate_metadata_path = self.candidate_dir / "skill_metadata_candidate.json"
            candidate_baseline_path = self.candidate_dir / "monitoring_baseline_candidate.json"
            joblib.dump(candidate_model, candidate_model_path)
            _write_candidate_metadata(candidate_metadata, candidate_metadata_path)

            if accepted:
                existing_baseline_version = None
                if self.baseline_path.is_file():
                    existing_baseline_version = load_monitoring_baseline(self.baseline_path).get("baseline_version")
                next_baseline = next_baseline_version(existing_baseline_version)
                create_monitoring_baseline(
                    data_path=self.dataset_path,
                    dataset_metadata_path=self.dataset_path.parent / "dataset_metadata.json",
                    model_path=candidate_model_path,
                    model_metadata_path=candidate_metadata_path,
                    output_path=candidate_baseline_path,
                    baseline_version=next_baseline,
                )

            mlflow_result = self._track_candidate(
                model=candidate_model,
                metadata=candidate_metadata,
                candidate_metrics=candidate_metrics,
                current_metrics=current_metrics,
                enable_mlflow=enable_mlflow,
            )
            candidate_metadata["mlflow"] = mlflow_result
            _write_candidate_metadata(candidate_metadata, candidate_metadata_path)

            if not accepted:
                return self._save_report(build_retraining_report(
                    status="rejected",
                    trigger=trigger["reason"],
                    old_model_version=old_version,
                    candidate_model_version=candidate_version,
                    dataset_version=data_version,
                    training_source=training_source,
                    candidate_metrics=candidate_metrics,
                    current_metrics=current_metrics,
                    rejection_reason=rejection_reason,
                    mlflow=mlflow_result,
                ))

            promotion = self.artifact_promoter.promote(
                candidate_model_path=candidate_model_path,
                candidate_metadata_path=candidate_metadata_path,
                candidate_baseline_path=candidate_baseline_path,
                expected_current_version=old_version,
                promotion_reason=trigger["reason"],
                gate=gate,
            )
            return self._save_report(build_retraining_report(
                status="promoted",
                trigger=trigger["reason"],
                old_model_version=old_version,
                candidate_model_version=promotion["model_version"],
                dataset_version=data_version,
                training_source=training_source,
                candidate_metrics=candidate_metrics,
                current_metrics=current_metrics,
                promotion_reason=gate["reason"],
                mlflow=mlflow_result,
                backup_files=promotion["backup_files"],
            ))
        except Exception as error:
            report = build_retraining_report(
                status="failed",
                trigger=trigger.get("reason", "unknown"),
                old_model_version=old_version,
                candidate_model_version=candidate_version,
                dataset_version=data_version,
                training_source=training_source,
                candidate_metrics=candidate_metrics,
                current_metrics=current_metrics,
                rejection_reason="retraining_failed",
                mlflow=mlflow_result,
                error=f"{type(error).__name__}: {error}",
            )
            return self._save_report(report)

    def _read_current_metadata(self) -> dict[str, Any]:
        try:
            value = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RetrainingDataError("Current model metadata is missing or invalid") from error
        if not isinstance(value, dict) or not isinstance(value.get("model_version"), str):
            raise RetrainingDataError("Current model metadata has no model_version")
        return value

    def _train_and_evaluate(
        self,
        *,
        dataset_frame: pd.DataFrame,
        dataset_metadata: dict[str, Any],
        current_metadata: dict[str, Any],
        current_model: Any,
        candidate_version: str,
    ) -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
        x = dataset_frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
        y = dataset_frame["target_skill"]
        x_train, x_valid, y_train, y_valid = train_test_split(
            x,
            y,
            test_size=0.2,
            random_state=42,
            stratify=y,
        )
        candidate_model = build_pipeline()
        candidate_model.fit(x_train, y_train)
        candidate_predictions = candidate_model.predict(x_valid)
        if len(candidate_predictions) != len(y_valid) or not set(candidate_predictions).issubset(SUPPORTED_SKILLS):
            raise RetrainingDataError("Candidate model produced invalid validation predictions")
        candidate_metrics = evaluate_model(candidate_model, x_valid, y_valid)
        current_metrics = evaluate_model(current_model, x_valid, y_valid)
        if candidate_metrics["validation_sample_count"] != current_metrics["validation_sample_count"]:
            raise RetrainingDataError("Current and candidate models used different validation samples")

        labels = sorted(SUPPORTED_SKILLS)
        candidate_metadata = {
            "model_name": "RandomForestClassifier",
            "model_version": candidate_version,
            "feature_version": current_metadata["feature_version"],
            "feature_names": NUMERIC_FEATURES + CATEGORICAL_FEATURES,
            "training_source": dataset_metadata.get("training_source", "unknown"),
            "dataset_version": dataset_metadata["dataset_version"],
            "dataset_path": str(self.dataset_path.resolve()),
            "sample_count": len(dataset_frame),
            "feature_count": len(NUMERIC_FEATURES + CATEGORICAL_FEATURES),
            "training_sample_count": len(dataset_frame),
            "training_split_count": len(x_train),
            "validation_sample_count": len(x_valid),
            "class_labels": labels,
            "training_timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": candidate_metrics,
            "training_data_note": "Synthetic development data is not real-world performance evidence." if dataset_metadata.get("training_source") == "synthetic_development_data" else "Labels follow the processed dataset's documented source.",
            "training_parameters": {
                "random_state": 42,
                "test_size": 0.2,
                "n_estimators": candidate_model.named_steps["classifier"].n_estimators,
                "max_depth": candidate_model.named_steps["classifier"].max_depth,
                "min_samples_split": candidate_model.named_steps["classifier"].min_samples_split,
                "min_samples_leaf": candidate_model.named_steps["classifier"].min_samples_leaf,
            },
        }
        return candidate_model, candidate_metadata, candidate_metrics, current_metrics

    @staticmethod
    def _track_candidate(
        *,
        model: Any,
        metadata: dict[str, Any],
        candidate_metrics: dict[str, Any],
        current_metrics: dict[str, Any],
        enable_mlflow: bool,
    ) -> dict[str, Any]:
        if not enable_mlflow:
            return {"status": "disabled", "reason": "Explicit offline/test mode; candidate was not registered"}
        from ml.tracking.mlflow_tracker import track_training_run

        params = {
            **metadata["training_parameters"],
            "promotion_decision": metadata["promotion_decision"],
            "current_accuracy": current_metrics["accuracy"],
            "current_f1": current_metrics["f1"],
        }
        metrics = {
            "accuracy": candidate_metrics["accuracy"],
            "precision": candidate_metrics["precision"],
            "recall": candidate_metrics["recall"],
            "f1": candidate_metrics["f1"],
            "candidate_accuracy": candidate_metrics["accuracy"],
            "candidate_f1": candidate_metrics["f1"],
            "current_accuracy": current_metrics["accuracy"],
            "current_f1": current_metrics["f1"],
            "validation_sample_count": candidate_metrics["validation_sample_count"],
            "training_sample_count": metadata["training_split_count"],
        }
        return track_training_run(
            model=model,
            metadata=metadata,
            params=params,
            metrics=metrics,
        )

    def _save_report(self, report: dict[str, Any]) -> dict[str, Any]:
        write_retraining_report(report, self.report_path)
        return report
