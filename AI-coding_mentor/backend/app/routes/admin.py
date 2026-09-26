from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends

from app.database.config import settings
from app.database.mongodb import get_mongodb_client
from app.routes.skill_ml import skill_model_health
from app.services.security import require_admin
from ml.monitoring.monitoring_service import get_monitoring_service
from ml.serving.skill_model_service import get_skill_model_service
from ml.tracking.mlflow_tracker import EXPERIMENT_NAME, REGISTERED_MODEL_NAME, configured_tracking_uri

router = APIRouter(prefix="/admin", tags=["admin"])

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MODEL_METADATA_PATH = BACKEND_ROOT / "ml" / "artifacts" / "skill_metadata.json"
RETRAINING_REPORT_PATH = BACKEND_ROOT / "ml" / "artifacts" / "retraining_report.json"
DVC_LOCK_PATH = BACKEND_ROOT / "dvc.lock"


def _status_from_bool(value: bool) -> str:
    return "configured" if value else "unavailable"


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        return json.loads(content) if content.strip() else None
    except (OSError, json.JSONDecodeError):
        return None


def _read_dvc_status() -> dict:
    if not DVC_LOCK_PATH.exists():
        return {"status": "unavailable", "pipeline": [], "dataset": "skill_training_data", "version": "unknown"}

    try:
        data = yaml.safe_load(DVC_LOCK_PATH.read_text(encoding="utf-8")) or {}
        stages = list((data or {}).get("stages", {}).keys())
        dataset_version = "unknown"
        processed_metadata = BACKEND_ROOT / "data" / "processed" / "dataset_metadata.json"
        if processed_metadata.exists():
            dataset_version = (json.loads(processed_metadata.read_text(encoding="utf-8")) or {}).get("dataset_version", "unknown")
        status = "up_to_date"
        if not stages:
            status = "unavailable"
        return {
            "status": status,
            "pipeline": stages,
            "dataset": "skill_training_data",
            "version": dataset_version,
        }
    except Exception:
        return {"status": "unavailable", "pipeline": [], "dataset": "skill_training_data", "version": "unknown"}


@router.get("/health")
def admin_health(_current_user: dict = Depends(require_admin)) -> dict:
    model_service = get_skill_model_service()
    health = skill_model_health(model_service=model_service)
    model_version = model_service.model_version or "unknown"
    feature_version = model_service.feature_version or "unknown"
    return {
        "backend": {
            "api_status": "healthy",
            "api_version": "0.1.0",
        },
        "database": {
            "status": _status_from_bool(get_mongodb_client() is not None),
            "configured": get_mongodb_client() is not None,
        },
        "judge0": {
            "status": _status_from_bool(bool(settings.judge0_url)),
            "configured": bool(settings.judge0_url),
        },
        "ml": {
            "status": "ready" if model_service.ready else "unavailable",
            "model_status": health.body.decode() if hasattr(health, "body") else ("ready" if model_service.ready else "unavailable"),
            "model_version": model_version,
            "feature_version": feature_version,
        },
        "mlops": {
            "mlflow_status": _status_from_bool(bool(configured_tracking_uri())),
            "dvc_status": _read_dvc_status()["status"],
        },
    }


@router.get("/ml-overview")
def ml_overview(_current_user: dict = Depends(require_admin)) -> dict:
    metadata = _read_json(MODEL_METADATA_PATH) or {}
    metrics = metadata.get("metrics") or {}
    model_version = metadata.get("model_version") or "unknown"
    feature_version = metadata.get("feature_version") or "unknown"
    dataset_version = metadata.get("dataset_version") or "unknown"
    training_source = metadata.get("training_source") or "unknown"
    experiment_name = metadata.get("mlflow_experiment") or EXPERIMENT_NAME
    run_id = metadata.get("mlflow_run_id") or None
    model_name = metadata.get("model_name") or "AI-Coding-Mentor-Skill-Predictor"
    model_type = model_name
    return {
        "model": {
            "name": "AI-Coding-Mentor-Skill-Predictor",
            "type": model_type,
            "version": model_version,
            "feature_version": feature_version,
            "artifact_status": "ready" if MODEL_METADATA_PATH.exists() else "unavailable",
        },
        "dataset": {
            "version": dataset_version,
            "dataset_source": training_source,
            "sample_count": metadata.get("training_sample_count") or metadata.get("sample_count") or 0,
            "feature_count": metadata.get("feature_count") or len(metadata.get("feature_names") or []),
        },
        "metrics": {
            "accuracy": metrics.get("accuracy"),
            "weighted_precision": metrics.get("precision"),
            "weighted_recall": metrics.get("recall"),
            "weighted_f1": metrics.get("f1") or metrics.get("f1_score"),
        },
        "training": {
            "training_source": training_source,
            "training_timestamp": metadata.get("training_timestamp"),
            "experiment_name": experiment_name,
            "run_id": run_id,
        },
    }


@router.get("/ml/monitoring")
def admin_monitoring(_current_user: dict = Depends(require_admin)) -> dict:
    report = get_monitoring_service().get_report()
    return {
        "status": report.get("status", "unavailable"),
        "prediction_count": report.get("prediction_count", 0),
        "minimum_required": report.get("minimum_required", 0),
        "monitoring_window": report.get("monitoring_window", {}),
        "baseline_version": report.get("baseline_version"),
        "model_version": report.get("model_version"),
        "feature_version": report.get("feature_version"),
        "dataset_version": report.get("dataset_version"),
        "feature_drift": report.get("feature_drift", []),
        "prediction_drift": report.get("prediction_drift"),
        "drifted_features": report.get("drifted_features", []),
        "warning_features": report.get("warning_features", []),
    }


@router.get("/ml/model")
def admin_model(_current_user: dict = Depends(require_admin)) -> dict:
    service = get_skill_model_service()
    metadata = service.metadata
    return {
        "model_name": "AI-Coding-Mentor-Skill-Predictor",
        "model_type": metadata.get("model_name") or "RandomForestClassifier",
        "model_version": service.model_version,
        "feature_version": service.feature_version,
        "artifact_status": "ready" if service.ready else "unavailable",
        "registry_status": (metadata.get("mlflow") or {}).get("registry_status", "not_available"),
    }


@router.get("/ml/retraining")
def admin_retraining(_current_user: dict = Depends(require_admin)) -> dict:
    report = _read_json(RETRAINING_REPORT_PATH)
    if not report:
        return {
            "status": "empty",
            "message": "No retraining history is available yet.",
            "history": [],
        }
    promotion = report.get("promotion") or {}
    gate = (promotion.get("gate") or {})
    return {
        "status": report.get("status", "unknown"),
        "trigger": report.get("trigger"),
        "current_model_version": report.get("old_model_version"),
        "candidate_model_version": report.get("candidate_model_version"),
        "candidate_metrics": report.get("candidate_metrics") or {},
        "current_metrics": report.get("current_metrics") or {},
        "promotion_decision": "promoted" if report.get("status") == "promoted" else ("rejected" if report.get("rejection_reason") else "pending"),
        "gate_result": gate.get("accepted"),
        "rejection_reason": report.get("rejection_reason"),
        "rollback_available": bool(report.get("backup_files")),
        "backup_files": [Path(item).name for item in (report.get("backup_files") or [])],
        "timestamp": report.get("timestamp"),
    }


@router.get("/ml/dataset")
def admin_dataset(_current_user: dict = Depends(require_admin)) -> dict:
    metadata = _read_json(BACKEND_ROOT / "data" / "processed" / "dataset_metadata.json") or {}
    return {
        "dataset": "skill_training_data",
        "version": metadata.get("dataset_version") or "unknown",
        "source": metadata.get("training_source") or "unknown",
        "sample_count": metadata.get("sample_count") or metadata.get("rows") or 0,
        "feature_count": metadata.get("feature_count") or 0,
        "status": "up_to_date" if metadata else "unavailable",
    }


@router.get("/mlflow")
def admin_mlflow(_current_user: dict = Depends(require_admin)) -> dict:
    metadata = _read_json(MODEL_METADATA_PATH) or {}
    mlflow_payload = metadata.get("mlflow") or {}
    tracking_uri = configured_tracking_uri()
    return {
        "experiment": mlflow_payload.get("experiment_name") or EXPERIMENT_NAME,
        "latest_run_id": mlflow_payload.get("run_id") or metadata.get("mlflow_run_id"),
        "model": "AI-Coding-Mentor-Skill-Predictor",
        "latest_registered_version": mlflow_payload.get("registry_version"),
        "tracking_status": "configured" if tracking_uri else "unavailable",
        "registry_status": mlflow_payload.get("registry_status") or "unavailable",
    }


@router.get("/dvc")
def admin_dvc(_current_user: dict = Depends(require_admin)) -> dict:
    return _read_dvc_status()


@router.get("/overview")
def admin_overview(_current_user: dict = Depends(require_admin)) -> dict:
    return {
        "system": admin_health(_current_user),
        "model": ml_overview(_current_user),
        "monitoring": admin_monitoring(_current_user),
        "retraining": admin_retraining(_current_user),
        "dataset": admin_dataset(_current_user),
        "mlflow": admin_mlflow(_current_user),
        "dvc": admin_dvc(_current_user),
    }
