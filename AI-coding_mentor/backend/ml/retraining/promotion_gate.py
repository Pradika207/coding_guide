"""Explicit, configurable minimum-quality gate for candidate models."""

from __future__ import annotations

from typing import Any

from app.database.config import settings


def evaluate_promotion_gate(
    candidate_metrics: dict[str, Any],
    current_metrics: dict[str, Any],
    *,
    minimum_accuracy: float | None = None,
    minimum_f1: float | None = None,
) -> dict[str, Any]:
    min_accuracy = settings.minimum_candidate_accuracy if minimum_accuracy is None else minimum_accuracy
    min_f1 = settings.minimum_candidate_f1 if minimum_f1 is None else minimum_f1
    required = ("accuracy", "precision", "recall", "f1", "validation_sample_count")
    missing_candidate = [name for name in required if name not in candidate_metrics]
    missing_current = [name for name in required if name not in current_metrics]
    if missing_candidate or missing_current:
        return {
            "accepted": False,
            "reason": "metrics_unavailable",
            "checks": {
                "candidate_metrics_available": not missing_candidate,
                "current_metrics_available": not missing_current,
            },
            "thresholds": {"minimum_accuracy": min_accuracy, "minimum_f1": min_f1},
        }

    checks = {
        "candidate_accuracy_meets_minimum": candidate_metrics["accuracy"] >= min_accuracy,
        "candidate_f1_meets_minimum": candidate_metrics["f1"] >= min_f1,
        "candidate_accuracy_not_below_current": candidate_metrics["accuracy"] >= current_metrics["accuracy"],
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "accepted": not failed,
        "reason": "candidate_passed_all_gates" if not failed else "candidate_failed_quality_gate",
        "checks": checks,
        "failed_checks": failed,
        "thresholds": {"minimum_accuracy": min_accuracy, "minimum_f1": min_f1},
    }