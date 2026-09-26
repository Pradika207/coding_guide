"""Load and serve the locally trained skill prediction model."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

import joblib

from ml.features.skill_features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_feature_row_from_rates,
    training_frame,
)

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "skill_model.joblib"
METADATA_PATH = ARTIFACT_DIR / "skill_metadata.json"
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


class SkillModelUnavailableError(RuntimeError):
    """Raised when the local model or its metadata cannot be served."""


class SkillPredictionFailure(RuntimeError):
    """Raised when a loaded model cannot produce a valid skill prediction."""


class SkillModelService:
    """A single loaded model instance with metadata-backed version information."""

    def __init__(
        self,
        *,
        model_path: Path = MODEL_PATH,
        metadata_path: Path = METADATA_PATH,
    ) -> None:
        self._model: Any | None = None
        self._metadata: dict[str, Any] = {}
        self._load_error: Exception | None = None
        self._load(model_path, metadata_path)

    def _load(self, model_path: Path, metadata_path: Path) -> None:
        try:
            if not model_path.is_file():
                raise FileNotFoundError("Skill model artifact is missing")
            if not metadata_path.is_file():
                raise FileNotFoundError("Skill model metadata is missing")

            model = joblib.load(model_path)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError("Skill model metadata must be a JSON object")
            if not callable(getattr(model, "predict", None)):
                raise TypeError("Skill model does not provide a predict method")

            model_version = metadata.get("model_version")
            feature_version = metadata.get("feature_version")
            feature_names = metadata.get("feature_names")
            class_labels = metadata.get("class_labels")
            if not isinstance(model_version, str) or not model_version.strip():
                raise ValueError("Skill model metadata has no model_version")
            if not isinstance(feature_version, str) or not feature_version.strip():
                raise ValueError("Skill model metadata has no feature_version")
            if feature_names != MODEL_FEATURES:
                raise ValueError("Skill model feature metadata does not match the serving schema")
            if not isinstance(class_labels, list) or not class_labels or not all(
                isinstance(label, str) for label in class_labels
            ):
                raise ValueError("Skill model metadata has no valid class_labels")

            self._model = model
            self._metadata = metadata
        except Exception as error:
            self._load_error = error
            logger.exception("Unable to load the local skill model and metadata")

    @property
    def ready(self) -> bool:
        return self._model is not None and not self._load_error

    @property
    def model_status(self) -> str:
        return "ready" if self.ready else "unavailable"

    @property
    def model_version(self) -> str | None:
        value = self._metadata.get("model_version")
        return value if isinstance(value, str) else None

    @property
    def feature_version(self) -> str | None:
        value = self._metadata.get("feature_version")
        return value if isinstance(value, str) else None

    @property
    def metadata(self) -> dict[str, Any]:
        """Return a copy of loaded metadata for internal callers and tests."""
        return dict(self._metadata)

    def predict(
        self,
        *,
        language: str,
        topic: str,
        assessment_accuracy: float,
        easy_success_rate: float,
        medium_success_rate: float,
        hard_success_rate: float,
        overall_success_rate: float,
        failure_rate: float,
        recent_success_rate: float,
        lesson_completion_rate: float,
        attempt_count: int,
        topic_count: int,
    ) -> str:
        if not self.ready or self._model is None:
            raise SkillModelUnavailableError("Skill prediction model is unavailable") from self._load_error

        # topic_count is validated request context, but the trained metadata's
        # feature_names do not include it, so it is intentionally not model input.
        _ = topic_count
        feature_row = build_feature_row_from_rates(
            language=language,
            topic=topic,
            assessment_accuracy=assessment_accuracy,
            easy_success_rate=easy_success_rate,
            medium_success_rate=medium_success_rate,
            hard_success_rate=hard_success_rate,
            overall_success_rate=overall_success_rate,
            failure_rate=failure_rate,
            recent_success_rate=recent_success_rate,
            lesson_completion_rate=lesson_completion_rate,
            attempt_count=attempt_count,
        )
        return self.predict_features(feature_row)

    def predict_features(self, feature_row: dict[str, Any]) -> str:
        if not self.ready or self._model is None:
            raise SkillModelUnavailableError("Skill prediction model is unavailable") from self._load_error
        try:
            if set(feature_row) != set(self._metadata["feature_names"]):
                raise ValueError("Request features do not match the trained model schema")
            feature_frame = training_frame([feature_row])[self._metadata["feature_names"]]
            predictions = self._model.predict(feature_frame)
            if len(predictions) != 1:
                raise ValueError("The model returned an unexpected prediction count")
            prediction = str(predictions[0])
            valid_labels = self._metadata.get("class_labels", [])
            if prediction not in valid_labels:
                raise ValueError("The model returned a class absent from its metadata")
            return prediction
        except Exception as error:
            logger.exception("Skill model prediction failed")
            raise SkillPredictionFailure("Skill prediction failed") from error


_service_instance: SkillModelService | None = None
_service_lock = Lock()


def get_skill_model_service() -> SkillModelService:
    """Return one process-wide lazy service, even under concurrent first use."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = SkillModelService(
                    model_path=MODEL_PATH,
                    metadata_path=METADATA_PATH,
                )
    return _service_instance


def reload_skill_model_service(*, expected_model_version: str | None = None) -> SkillModelService:
    """Load and atomically publish a replacement serving instance after promotion."""
    global _service_instance
    replacement = SkillModelService(model_path=MODEL_PATH, metadata_path=METADATA_PATH)
    if not replacement.ready:
        raise SkillModelUnavailableError("Promoted model artifacts could not be loaded")
    if expected_model_version and replacement.model_version != expected_model_version:
        raise SkillModelUnavailableError("Promoted model version does not match expected version")
    with _service_lock:
        _service_instance = replacement
    return replacement