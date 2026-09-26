"""Aggregate recent, version-matched prediction logs into a drift report."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any, Callable

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.database.config import settings
from ml.features.skill_features import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from ml.monitoring.baseline import DEFAULT_BASELINE_PATH, load_monitoring_baseline
from ml.monitoring.drift_detector import (
    compare_categorical_feature,
    compare_numeric_feature,
    compare_prediction_distribution,
)
from ml.monitoring.prediction_logger import get_prediction_collection
from ml.serving.skill_model_service import SkillModelService, get_skill_model_service

logger = logging.getLogger(__name__)

PROJECTION = {
    "_id": 0,
    "timestamp": 1,
    "model_version": 1,
    "feature_version": 1,
    "language": 1,
    "topic": 1,
    "prediction": 1,
    "features": 1,
}


class MonitoringService:
    def __init__(
        self,
        *,
        baseline_path: Path = DEFAULT_BASELINE_PATH,
        prediction_collection_provider: Callable[[], Collection] = get_prediction_collection,
        model_service_provider: Callable[[], SkillModelService] = get_skill_model_service,
        minimum_predictions: int | None = None,
        window_size: int | None = None,
    ) -> None:
        self._baseline_path = baseline_path
        self._prediction_collection_provider = prediction_collection_provider
        self._model_service_provider = model_service_provider
        self._minimum_predictions = minimum_predictions or settings.ml_monitoring_minimum_predictions
        self._window_size = window_size or settings.ml_monitoring_window_size

    def get_baseline(self) -> dict[str, Any]:
        return load_monitoring_baseline(self._baseline_path)

    def get_report(self) -> dict[str, Any]:
        try:
            baseline = self.get_baseline()
        except (OSError, ValueError) as error:
            logger.exception("Monitoring baseline is unavailable")
            return {
                "status": "unavailable",
                "reason": "monitoring_baseline_unavailable",
                "prediction_count": 0,
                "total_monitored_predictions": 0,
                "minimum_required": self._minimum_predictions,
                "feature_drift": [],
                "prediction_drift": None,
            }

        model_service = self._model_service_provider()
        model_version = model_service.model_version or baseline.get("model_version")
        feature_version = model_service.feature_version or baseline.get("feature_version")
        if not model_service.ready:
            return self._unavailable_report(model_version, feature_version, baseline, "model_unavailable")
        if baseline.get("model_version") != model_version or baseline.get("feature_version") != feature_version:
            return self._unavailable_report(model_version, feature_version, baseline, "baseline_version_mismatch")
        baseline_training_count = baseline.get("model_training_sample_count")
        model_training_count = model_service.metadata.get("training_sample_count")
        if (
            baseline_training_count is not None
            and model_training_count is not None
            and baseline_training_count != model_training_count
        ):
            return self._unavailable_report(model_version, feature_version, baseline, "baseline_model_artifact_mismatch")

        try:
            collection = self._prediction_collection_provider()
            cursor = collection.find(
                {"model_version": model_version, "feature_version": feature_version},
                PROJECTION,
            ).sort("timestamp", -1).limit(self._window_size)
            records = [record for record in cursor if self._valid_record(record)]
        except (PyMongoError, RuntimeError, OSError) as error:
            logger.error(
                "Prediction monitoring window is unavailable (%s)",
                type(error).__name__,
            )
            return self._unavailable_report(model_version, feature_version, baseline, "prediction_storage_unavailable")

        records = records[:self._window_size]
        result_base: dict[str, Any] = {
            "model_version": model_version,
            "feature_version": feature_version,
            "baseline_version": baseline.get("baseline_version"),
            "dataset_version": baseline.get("dataset_version"),
            "prediction_count": len(records),
            "total_monitored_predictions": len(records),
            "minimum_required": self._minimum_predictions,
            "monitoring_window": {
                "type": "last_n_predictions",
                "maximum_predictions": self._window_size,
                "measured_from": self._timestamp(records[-1].get("timestamp")) if records else None,
                "measured_to": self._timestamp(records[0].get("timestamp")) if records else None,
            },
            "feature_drift": [],
            "prediction_drift": None,
            "drifted_features": [],
            "warning_features": [],
            "scope_note": "Status describes measured distribution drift in this prediction window only; it is not a general model-health or accuracy assessment.",
        }
        if len(records) < self._minimum_predictions:
            return {"status": "insufficient_data", **result_base}

        feature_drift = [
            compare_numeric_feature(
                feature,
                [record["features"][feature] for record in records],
                baseline["numeric_features"][feature],
            )
            for feature in NUMERIC_FEATURES
        ]
        feature_drift.extend(
            compare_categorical_feature(
                feature,
                [record[feature] for record in records],
                baseline["categorical_features"][feature],
            )
            for feature in CATEGORICAL_FEATURES
        )
        prediction_drift = compare_prediction_distribution(
            [record["prediction"] for record in records],
            baseline["prediction_distribution"],
        )
        all_results = [*feature_drift, prediction_drift]
        drifted = [item["feature"] for item in all_results if item["status"] == "drift"]
        warnings = [item["feature"] for item in all_results if item["status"] == "warning"]
        overall_status = "drift" if drifted else "warning" if warnings else "stable"
        return {
            "status": overall_status,
            **result_base,
            "feature_drift": feature_drift,
            "prediction_drift": prediction_drift,
            "drifted_features": drifted,
            "warning_features": warnings,
        }

    @staticmethod
    def _valid_record(record: dict[str, Any]) -> bool:
        if not isinstance(record, dict) or not isinstance(record.get("features"), dict):
            return False
        if not isinstance(record.get("prediction"), str):
            return False
        if not all(isinstance(record.get(name), str) for name in CATEGORICAL_FEATURES):
            return False
        try:
            return all(
                name in record["features"] and isfinite(float(record["features"][name]))
                for name in NUMERIC_FEATURES
            )
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _timestamp(value: Any) -> str | None:
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    def _unavailable_report(
        self,
        model_version: str | None,
        feature_version: str | None,
        baseline: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "reason": reason,
            "model_version": model_version,
            "feature_version": feature_version,
            "baseline_version": baseline.get("baseline_version"),
            "dataset_version": baseline.get("dataset_version"),
            "prediction_count": 0,
            "total_monitored_predictions": 0,
            "minimum_required": self._minimum_predictions,
            "feature_drift": [],
            "prediction_drift": None,
            "drifted_features": [],
            "warning_features": [],
            "scope_note": "Drift status is unavailable because required monitoring inputs could not be read.",
        }


_monitoring_service: MonitoringService | None = None


def get_monitoring_service() -> MonitoringService:
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service