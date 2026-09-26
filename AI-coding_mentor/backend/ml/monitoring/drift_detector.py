"""Small, deterministic Population Stability Index drift comparisons."""

from __future__ import annotations

from bisect import bisect_right
from math import isfinite, log
from typing import Any, Iterable

from ml.monitoring.baseline import _bin_index

WARNING_THRESHOLD = 0.10
DRIFT_THRESHOLD = 0.20
PSI_EPSILON = 1e-6


def status_for_score(score: float) -> str:
    if score >= DRIFT_THRESHOLD:
        return "drift"
    if score >= WARNING_THRESHOLD:
        return "warning"
    return "stable"


def population_stability_index(expected: list[float], actual: list[float]) -> float:
    """Compute PSI from corresponding expected and actual bin proportions."""
    if len(expected) != len(actual) or not expected:
        raise ValueError("PSI distributions must have the same non-empty number of bins")
    score = 0.0
    for expected_share, actual_share in zip(expected, actual):
        expected_share = max(float(expected_share), PSI_EPSILON)
        actual_share = max(float(actual_share), PSI_EPSILON)
        score += (actual_share - expected_share) * log(actual_share / expected_share)
    return score if isfinite(score) else 0.0


def compare_numeric_feature(
    feature: str,
    values: Iterable[float],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    current_values = [float(value) for value in values]
    histogram = baseline.get("histogram", {})
    edges = histogram.get("edges", [])
    expected = histogram.get("proportions", [])
    if not current_values or len(edges) < 2 or len(expected) != len(edges) - 1:
        raise ValueError(f"Cannot compare numeric feature {feature!r} with invalid data")
    counts = [0] * len(expected)
    for value in current_values:
        counts[_bin_index(value, edges)] += 1
    actual = [count / len(current_values) for count in counts]
    score = population_stability_index(expected, actual)
    return {
        "feature": feature,
        "kind": "numeric",
        "method": "population_stability_index",
        "drift_score": score,
        "threshold": DRIFT_THRESHOLD,
        "warning_threshold": WARNING_THRESHOLD,
        "status": status_for_score(score),
        "sample_count": len(current_values),
    }


def compare_categorical_feature(
    feature: str,
    values: Iterable[str],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    current_values = [str(value) for value in values]
    expected_distribution = baseline.get("proportions", {})
    if not current_values or not expected_distribution:
        raise ValueError(f"Cannot compare categorical feature {feature!r} with invalid data")
    counts: dict[str, int] = {}
    for value in current_values:
        counts[value] = counts.get(value, 0) + 1
    labels = sorted(set(expected_distribution) | set(counts))
    expected = [float(expected_distribution.get(label, 0.0)) for label in labels]
    actual = [counts.get(label, 0) / len(current_values) for label in labels]
    score = population_stability_index(expected, actual)
    return {
        "feature": feature,
        "kind": "categorical",
        "method": "population_stability_index",
        "drift_score": score,
        "threshold": DRIFT_THRESHOLD,
        "warning_threshold": WARNING_THRESHOLD,
        "status": status_for_score(score),
        "sample_count": len(current_values),
        "current_distribution": {
            label: counts.get(label, 0) / len(current_values) for label in labels
        },
    }


def compare_prediction_distribution(
    values: Iterable[str],
    baseline_distribution: dict[str, Any],
) -> dict[str, Any]:
    result = compare_categorical_feature(
        "prediction_distribution",
        values,
        baseline_distribution,
    )
    result["kind"] = "prediction_distribution"
    return result