"""MLflow experiment tracking isolated from training and inference code."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import sklearn

EXPERIMENT_NAME = "AI-Coding-Mentor-Skill-Prediction"
REGISTERED_MODEL_NAME = "AI-Coding-Mentor-Skill-Predictor"
DEFAULT_TRACKING_URI = "http://127.0.0.1:5000"


def local_tracking_uri(root: Path | None = None) -> str:
    tracking_dir = root or (Path(__file__).resolve().parents[2] / "mlruns")
    tracking_dir.mkdir(parents=True, exist_ok=True)
    return tracking_dir.resolve().as_uri()


def configured_tracking_uri() -> str:
    return os.getenv("MLFLOW_TRACKING_URI", DEFAULT_TRACKING_URI).strip() or DEFAULT_TRACKING_URI


def _log_run(
    *,
    mlflow: Any,
    model: Any,
    metadata: dict[str, Any],
    params: dict[str, Any],
    metrics: dict[str, float],
    tracking_uri: str,
    experiment_name: str,
    registered_model_name: str | None,
) -> dict[str, Any]:
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=metadata.get("model_version", "skill-model-v1")) as run:
        for key, value in params.items():
            if value is not None:
                mlflow.log_param(key, value)
        mlflow.log_params({
            "model_type": metadata.get("model_name", "RandomForestClassifier"),
            "model_version": metadata.get("model_version", "skill-model-v1"),
            "feature_version": metadata.get("feature_version", "features-v1"),
            "training_source": metadata.get("training_source", "unknown"),
            "sample_count": metadata.get("training_sample_count", 0),
            "number_of_features": len(metadata.get("feature_names", [])),
            "feature_count": metadata.get("feature_count", len(metadata.get("feature_names", []))),
            "class_count": len(metadata.get("class_labels", [])),
            "dataset_version": metadata.get("dataset_version", "unknown"),
            "dataset_path": metadata.get("dataset_path", "not_provided"),
            **params,
        })
        mlflow.set_tags({
            "project": "AI-Coding-Mentor",
            "component": "skill-prediction",
            "model_version": metadata.get("model_version", "skill-model-v1"),
            "feature_version": metadata.get("feature_version", "features-v1"),
            "training_source": metadata.get("training_source", "unknown"),
            "data_source": metadata.get("training_source", "unknown"),
        })
        for name, value in metrics.items():
            mlflow.log_metric(name, float(value))
        logged_model = mlflow.sklearn.log_model(
            model,
            name="skill_predictor",
            serialization_format="cloudpickle",
            pip_requirements=[f"scikit-learn=={sklearn.__version__}"],
        )

        registry_status = "not_registered"
        registry_version = None
        model_uri = getattr(logged_model, "model_uri", None) or f"runs:/{run.info.run_id}/skill_predictor"
        if registered_model_name:
            try:
                registered = mlflow.register_model(model_uri, registered_model_name)
                registry_status = "registered"
                registry_version = str(registered.version)
            except Exception as error:  # Registry availability varies by tracking backend.
                registry_status = f"unavailable: {type(error).__name__}"
        else:
            registry_status = "skipped"

        metadata_with_run = {
            **metadata,
            "mlflow_experiment": experiment_name,
            "mlflow_run_id": run.info.run_id,
            "mlflow_run_name": run.info.run_name,
            "mlflow_tracking_uri": tracking_uri,
            "registry_status": registry_status,
            "registry_version": registry_version,
            "model_uri": model_uri,
        }
        mlflow.log_dict(metadata_with_run, "skill_metadata.json")

        return {
            "status": "tracked",
            "tracking_uri": tracking_uri,
            "experiment_name": experiment_name,
            "run_id": run.info.run_id,
            "run_name": run.info.run_name,
            "registered_model_name": registered_model_name,
            "registry_status": registry_status,
            "registry_version": registry_version,
            "model_uri": model_uri,
        }


def track_training_run(
    *,
    model: Any,
    metadata: dict[str, Any],
    params: dict[str, Any],
    metrics: dict[str, float],
    tracking_uri: str | None = None,
    experiment_name: str = EXPERIMENT_NAME,
    registered_model_name: str | None = REGISTERED_MODEL_NAME,
    fallback_dir: Path | None = None,
) -> dict[str, Any]:
    """Track a successful model; retry with local file tracking if a server fails."""
    try:
        import mlflow
    except ImportError as error:
        return {"status": "unavailable", "reason": f"MLflow import failed: {error}"}

    selected_uri = tracking_uri or configured_tracking_uri()
    if selected_uri.startswith("file:"):
        # MLflow 3 gates its legacy local file store behind an explicit opt-in.
        # A caller that explicitly selects a file URI is requesting local tracking.
        os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    try:
        return _log_run(
            mlflow=mlflow,
            model=model,
            metadata=metadata,
            params=params,
            metrics=metrics,
            tracking_uri=selected_uri,
            experiment_name=experiment_name,
            registered_model_name=registered_model_name,
        )
    except Exception as primary_error:
        if selected_uri.startswith("file:"):
            return {
                "status": "unavailable",
                "tracking_uri": selected_uri,
                "reason": f"Tracking failed: {type(primary_error).__name__}",
            }
        fallback_uri = local_tracking_uri(fallback_dir)
        # MLflow 3 gates its legacy local file store behind an explicit opt-in.
        # Set this only for the fallback call, not for server-backed tracking.
        os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
        try:
            result = _log_run(
                mlflow=mlflow,
                model=model,
                metadata=metadata,
                params=params,
                metrics=metrics,
                tracking_uri=fallback_uri,
                experiment_name=experiment_name,
                registered_model_name=registered_model_name,
            )
            result["fallback_used"] = True
            result["configured_tracking_uri"] = selected_uri
            return result
        except Exception as fallback_error:
            return {
                "status": "unavailable",
                "tracking_uri": fallback_uri,
                "configured_tracking_uri": selected_uri,
                "reason": (
                    f"Server tracking failed: {type(primary_error).__name__}: {primary_error}; "
                    f"local tracking failed: {type(fallback_error).__name__}: {fallback_error}"
                ),
            }
