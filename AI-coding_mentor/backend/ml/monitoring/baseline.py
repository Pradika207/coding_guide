"""Create and load a deterministic feature and prediction baseline artifact."""

from __future__ import annotations

import csv
import json
import math
from bisect import bisect_right
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import joblib

from ml.features.skill_features import CATEGORICAL_FEATURES, NUMERIC_FEATURES

BASELINE_VERSION = "baseline-v1"
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = BACKEND_ROOT / "data" / "processed" / "skill_training_data_processed.csv"
DEFAULT_DATASET_METADATA_PATH = DEFAULT_DATA_PATH.parent / "dataset_metadata.json"
DEFAULT_MODEL_PATH = BACKEND_ROOT / "ml" / "artifacts" / "skill_model.joblib"
DEFAULT_MODEL_METADATA_PATH = BACKEND_ROOT / "ml" / "artifacts" / "skill_metadata.json"
DEFAULT_BASELINE_PATH = BACKEND_ROOT / "ml" / "artifacts" / "monitoring_baseline.json"
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
QUANTILES = (0.05, 0.25, 0.50, 0.75, 0.95)


def _quantile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _make_bin_edges(sorted_values: list[float]) -> list[float]:
    edges = sorted({_quantile(sorted_values, step / 10) for step in range(11)})
    if len(edges) < 2:
        value = edges[0]
        padding = max(abs(value) * 0.01, 0.5)
        edges = [value - padding, value + padding]
    return edges


def _bin_index(value: float, edges: list[float]) -> int:
    return max(0, min(bisect_right(edges[1:-1], value), len(edges) - 2))


def _distribution(values: list[str]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    total = len(values)
    return {
        "counts": dict(sorted(counts.items())),
        "proportions": {
            key: count / total for key, count in sorted(counts.items())
        } if total else {},
    }


def create_monitoring_baseline(
    *,
    data_path: Path = DEFAULT_DATA_PATH,
    dataset_metadata_path: Path = DEFAULT_DATASET_METADATA_PATH,
    model_path: Path = DEFAULT_MODEL_PATH,
    model_metadata_path: Path = DEFAULT_MODEL_METADATA_PATH,
    output_path: Path = DEFAULT_BASELINE_PATH,
    baseline_version: str = BASELINE_VERSION,
) -> dict[str, Any]:
    """Derive a stable JSON baseline from prepared data and the local model."""
    with data_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        available = set(reader.fieldnames or [])
        missing = set(FEATURE_COLUMNS + ["skill_level"]) - available
        if missing:
            raise ValueError(f"Processed dataset is missing baseline columns: {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError("Processed dataset has no rows for a monitoring baseline")

    dataset_metadata = json.loads(dataset_metadata_path.read_text(encoding="utf-8"))
    model_metadata = json.loads(model_metadata_path.read_text(encoding="utf-8"))
    if not dataset_metadata.get("dataset_version"):
        raise ValueError("Processed dataset metadata has no dataset_version")
    if model_metadata.get("feature_names") != FEATURE_COLUMNS:
        raise ValueError("Model metadata feature_names do not match monitoring features")
    if not model_metadata.get("model_version") or not model_metadata.get("feature_version"):
        raise ValueError("Model metadata must contain model_version and feature_version")
    if not model_path.is_file():
        raise FileNotFoundError("Skill model artifact is required to build prediction baseline")

    numeric_values: dict[str, list[float]] = {
        feature: [float(row[feature]) for row in rows] for feature in NUMERIC_FEATURES
    }
    numeric_baseline: dict[str, dict[str, Any]] = {}
    for feature, values in numeric_values.items():
        ordered = sorted(values)
        edges = _make_bin_edges(ordered)
        counts = [0] * (len(edges) - 1)
        for value in values:
            counts[_bin_index(value, edges)] += 1
        numeric_baseline[feature] = {
            "mean": mean(values),
            "standard_deviation": pstdev(values),
            "minimum": ordered[0],
            "maximum": ordered[-1],
            "quantiles": {
                f"p{int(probability * 100):02d}": _quantile(ordered, probability)
                for probability in QUANTILES
            },
            "histogram": {
                "edges": edges,
                "proportions": [count / len(values) for count in counts],
            },
        }

    import pandas as pd

    feature_frame = pd.DataFrame(
        [{feature: float(row[feature]) for feature in NUMERIC_FEATURES} | {
            feature: row[feature] for feature in CATEGORICAL_FEATURES
        } for row in rows]
    )[model_metadata["feature_names"]]
    model = joblib.load(model_path)
    baseline_predictions = [str(value) for value in model.predict(feature_frame)]
    baseline = {
        "baseline_version": baseline_version,
        "dataset_version": dataset_metadata["dataset_version"],
        "training_source": dataset_metadata.get("training_source", "unknown"),
        "feature_version": model_metadata["feature_version"],
        "model_version": model_metadata["model_version"],
        "model_training_sample_count": model_metadata.get("training_sample_count"),
        "sample_count": len(rows),
        "target_column": "skill_level",
        "numeric_features": numeric_baseline,
        "categorical_features": {
            feature: _distribution([row[feature] for row in rows])
            for feature in CATEGORICAL_FEATURES
        },
        "prediction_distribution": _distribution(baseline_predictions),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(baseline, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return baseline


def load_monitoring_baseline(path: Path = DEFAULT_BASELINE_PATH) -> dict[str, Any]:
    baseline = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(baseline, dict):
        raise ValueError("Monitoring baseline must be a JSON object")
    return baseline