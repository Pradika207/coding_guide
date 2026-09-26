"""Internal-only restoration of a previously promoted artifact triple."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml.models.skill_predictor import ARTIFACT_DIR, METADATA_PATH
from ml.retraining.artifact_promoter import ArtifactPromoter, PromotionError


class RollbackService:
    def __init__(
        self,
        *,
        backup_dir: Path | None = None,
        metadata_path: Path = METADATA_PATH,
        promoter: ArtifactPromoter | None = None,
    ) -> None:
        self.backup_dir = backup_dir or ARTIFACT_DIR / "backups"
        self.metadata_path = metadata_path
        self.promoter = promoter or ArtifactPromoter(backup_dir=self.backup_dir)

    def rollback_to_version(self, model_version: str) -> dict[str, Any]:
        if not self.metadata_path.is_file():
            raise PromotionError("Current model metadata is unavailable")
        current_metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        current_version = current_metadata.get("model_version")
        if current_version == model_version:
            raise PromotionError("Requested model version is already active")

        prefix = f"skill_model_{model_version}"
        model_backups = sorted(self.backup_dir.glob(f"{prefix}*.joblib"))
        for model_backup in model_backups:
            suffix = model_backup.stem[len(prefix):]
            metadata_backup = self.backup_dir / f"skill_metadata_{model_version}{suffix}.json"
            if not metadata_backup.is_file():
                continue
            for baseline_backup in sorted(self.backup_dir.glob("monitoring_baseline_*.json")):
                try:
                    baseline = json.loads(baseline_backup.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if baseline.get("model_version") != model_version:
                    continue
                result = self.promoter.restore(
                    model_backup_path=model_backup,
                    metadata_backup_path=metadata_backup,
                    baseline_backup_path=baseline_backup,
                    expected_current_version=current_version,
                )
                return {
                    "status": "rolled_back",
                    "model_version": result["model_version"],
                    "feature_version": result["feature_version"],
                    "restored_from": model_backup.name,
                    "backup_files": result["backup_files"],
                }
        raise PromotionError(f"No complete model/metadata/baseline backup exists for {model_version}")
