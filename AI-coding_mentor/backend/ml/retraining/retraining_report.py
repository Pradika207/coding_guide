"""Structured report construction and persistence for retraining runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ml.models.skill_predictor import ARTIFACT_DIR

REPORT_PATH = ARTIFACT_DIR / "retraining_report.json"


def build_retraining_report(
    *,
    status: str,
    trigger: str,
    old_model_version: str | None,
    candidate_model_version: str | None = None,
    dataset_version: str | None = None,
    training_source: str | None = None,
    candidate_metrics: dict[str, Any] | None = None,
    current_metrics: dict[str, Any] | None = None,
    promotion_reason: str | None = None,
    rejection_reason: str | None = None,
    mlflow: dict[str, Any] | None = None,
    backup_files: list[str] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "trigger": trigger,
        "old_model_version": old_model_version,
        "candidate_model_version": candidate_model_version,
        "dataset_version": dataset_version,
        "training_source": training_source,
        "candidate_metrics": candidate_metrics,
        "current_metrics": current_metrics,
        "promotion_reason": promotion_reason,
        "rejection_reason": rejection_reason,
        "mlflow": mlflow or {"status": "not_attempted"},
        "backup_files": backup_files or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error": error,
    }


def write_retraining_report(report: dict[str, Any], path: Path = REPORT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path