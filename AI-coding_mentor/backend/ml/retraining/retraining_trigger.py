"""Deterministic decision boundary between monitoring and training."""

from __future__ import annotations

from typing import Any

from app.database.config import settings


def determine_retraining_need(
    monitoring_report: dict[str, Any],
    *,
    new_training_rows: int = 0,
    force: bool = False,
    minimum_new_rows: int | None = None,
) -> dict[str, Any]:
    if force:
        return {
            "retrain_required": True,
            "reason": "manual",
            "drifted_features": [],
        }

    report_status = monitoring_report.get("status")
    if report_status == "insufficient_data":
        return {
            "retrain_required": False,
            "reason": "insufficient_monitoring_data",
            "drifted_features": [],
        }
    if report_status == "unavailable":
        return {
            "retrain_required": False,
            "reason": "monitoring_unavailable",
            "drifted_features": [],
        }

    drifted_features = sorted(set(monitoring_report.get("drifted_features", [])))
    if report_status == "drift" or drifted_features:
        return {
            "retrain_required": True,
            "reason": "feature_drift",
            "drifted_features": drifted_features,
        }

    minimum = minimum_new_rows or settings.minimum_new_training_rows
    if new_training_rows >= minimum:
        return {
            "retrain_required": True,
            "reason": "new_training_data",
            "drifted_features": [],
        }
    return {
        "retrain_required": False,
        "reason": "no_retraining_trigger",
        "drifted_features": [],
    }