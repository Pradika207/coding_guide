"""Privacy-conscious persistence for successful model predictions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.database.mongodb import get_database
from ml.features.skill_features import NUMERIC_FEATURES

logger = logging.getLogger(__name__)


def get_prediction_collection() -> Collection:
    """Get the separate prediction collection and ensure its query indexes."""
    collection = get_database()["ml_predictions"]
    collection.create_index("prediction_id", unique=True)
    collection.create_index("timestamp")
    collection.create_index([
        ("model_version", 1),
        ("feature_version", 1),
        ("timestamp", -1),
    ])
    return collection


class PredictionLogger:
    """Log aggregate inference context only; never user identity or credentials."""

    def __init__(self, collection_provider: Callable[[], Collection] = get_prediction_collection):
        self._collection_provider = collection_provider

    def log_prediction(
        self,
        *,
        features: dict[str, Any],
        prediction: str,
        model_version: str,
        feature_version: str,
    ) -> bool:
        numeric_features = {
            name: float(features[name]) if name != "attempt_count" else int(features[name])
            for name in NUMERIC_FEATURES
            if name in features
        }
        if set(numeric_features) != set(NUMERIC_FEATURES):
            logger.error("Prediction was not logged because its model features were incomplete")
            return False

        document = {
            "prediction_id": uuid4().hex,
            "timestamp": datetime.now(timezone.utc),
            "model_version": model_version,
            "feature_version": feature_version,
            "language": str(features["language"]),
            "topic": str(features["topic"]),
            "prediction": prediction,
            "features": numeric_features,
        }
        try:
            self._collection_provider().insert_one(document)
        except (PyMongoError, RuntimeError, OSError) as error:
            # Monitoring storage must not make otherwise successful inference fail.
            logger.error(
                "Unable to persist skill prediction monitoring record (%s)",
                type(error).__name__,
            )
            return False
        return True


_prediction_logger = PredictionLogger()


def log_prediction(
    *,
    features: dict[str, Any],
    prediction: str,
    model_version: str,
    feature_version: str,
) -> bool:
    return _prediction_logger.log_prediction(
        features=features,
        prediction=prediction,
        model_version=model_version,
        feature_version=feature_version,
    )