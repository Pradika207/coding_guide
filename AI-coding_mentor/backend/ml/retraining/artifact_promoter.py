"""Back up and atomically replace the active model, metadata, and baseline."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

import joblib

from ml.monitoring.baseline import DEFAULT_BASELINE_PATH
from ml.models.skill_predictor import ARTIFACT_DIR, METADATA_PATH, MODEL_PATH
from ml.serving.skill_model_service import (
    SkillModelService,
    reload_skill_model_service,
)


class PromotionError(RuntimeError):
    """Raised when candidate validation or artifact promotion fails."""


class ArtifactPromoter:
    def __init__(
        self,
        *,
        model_path: Path = MODEL_PATH,
        metadata_path: Path = METADATA_PATH,
        baseline_path: Path = DEFAULT_BASELINE_PATH,
        backup_dir: Path | None = None,
        serving_reloader: Callable[..., SkillModelService] = reload_skill_model_service,
    ) -> None:
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.baseline_path = baseline_path
        self.backup_dir = backup_dir or ARTIFACT_DIR / "backups"
        self._serving_reloader = serving_reloader

    def promote(
        self,
        *,
        candidate_model_path: Path,
        candidate_metadata_path: Path,
        candidate_baseline_path: Path,
        expected_current_version: str,
        promotion_reason: str,
        gate: dict[str, Any],
    ) -> dict[str, Any]:
        current_metadata = self._read_json(self.metadata_path)
        candidate_metadata = self._read_json(candidate_metadata_path)
        candidate_baseline = self._read_json(candidate_baseline_path)
        new_version = candidate_metadata.get("model_version")
        feature_version = candidate_metadata.get("feature_version")
        if current_metadata.get("model_version") != expected_current_version:
            raise PromotionError("Active model changed before candidate promotion")
        if not self.baseline_path.is_file():
            raise PromotionError("Current monitoring baseline is required for paired promotion")
        if not isinstance(new_version, str) or not isinstance(feature_version, str):
            raise PromotionError("Candidate model metadata is missing its versions")
        if candidate_baseline.get("model_version") != new_version:
            raise PromotionError("Candidate baseline model version does not match candidate metadata")
        if candidate_baseline.get("feature_version") != feature_version:
            raise PromotionError("Candidate baseline feature version does not match candidate metadata")
        if not candidate_model_path.is_file():
            raise PromotionError("Candidate model artifact is missing")
        # Fully load/validate candidate files before touching active artifacts.
        candidate_service = SkillModelService(
            model_path=candidate_model_path,
            metadata_path=candidate_metadata_path,
        )
        if not candidate_service.ready or candidate_service.model_version != new_version:
            raise PromotionError("Candidate model and metadata failed serving validation")
        try:
            loaded_candidate = joblib.load(candidate_model_path)
            if not callable(getattr(loaded_candidate, "predict", None)):
                raise TypeError("Candidate artifact has no predict method")
        except Exception as error:
            raise PromotionError("Candidate model artifact could not be loaded") from error

        promotion_metadata = {
            **candidate_metadata,
            "promotion": {
                "status": "promoted",
                "promoted_from": expected_current_version,
                "reason": promotion_reason,
                "gate": gate,
            },
        }
        if candidate_baseline.get("model_training_sample_count") is not None:
            if candidate_baseline["model_training_sample_count"] != candidate_metadata.get("training_sample_count"):
                raise PromotionError("Candidate baseline was built for a different training sample count")

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backup_paths = self._backup_active_files(expected_current_version)
        replacements: list[tuple[Path, Path]] = [
            (candidate_model_path, self.model_path),
            (self._write_json_stage(promotion_metadata, self.metadata_path), self.metadata_path),
            (candidate_baseline_path, self.baseline_path),
        ]
        replaced: list[Path] = []
        try:
            for source, destination in replacements:
                destination.parent.mkdir(parents=True, exist_ok=True)
                staged = self._stage_copy(source, destination)
                os.replace(staged, destination)
                replaced.append(destination)
            loaded_service = self._serving_reloader(expected_model_version=new_version)
            if loaded_service.model_version != new_version or loaded_service.feature_version != feature_version:
                raise PromotionError("Serving and promoted model metadata versions do not match")
        except Exception as error:
            restore_errors = self._restore_active_files(backup_paths, replaced)
            try:
                self._serving_reloader(expected_model_version=expected_current_version)
            except Exception as reload_error:
                restore_errors.append(reload_error)
            if restore_errors:
                raise PromotionError("Promotion failed and artifact rollback was incomplete") from error
            if isinstance(error, PromotionError):
                raise
            raise PromotionError("Candidate promotion failed; the previous model was restored") from error
        finally:
            for source, _ in replacements:
                if source.name.startswith(".") and source.exists():
                    source.unlink(missing_ok=True)

        return {
            "model_version": new_version,
            "feature_version": feature_version,
            "backup_files": [str(path) for path in backup_paths.values()],
        }

    def restore(
        self,
        *,
        model_backup_path: Path,
        metadata_backup_path: Path,
        baseline_backup_path: Path,
        expected_current_version: str,
    ) -> dict[str, Any]:
        """Restore a matching backup triple while backing up the active triple."""
        current_metadata = self._read_json(self.metadata_path)
        restored_metadata = self._read_json(metadata_backup_path)
        restored_baseline = self._read_json(baseline_backup_path)
        restored_version = restored_metadata.get("model_version")
        feature_version = restored_metadata.get("feature_version")
        if current_metadata.get("model_version") != expected_current_version:
            raise PromotionError("Active model changed before rollback")
        if not isinstance(restored_version, str) or not isinstance(feature_version, str):
            raise PromotionError("Backup metadata is missing model/feature versions")
        if restored_baseline.get("model_version") != restored_version:
            raise PromotionError("Backup model and monitoring baseline versions do not match")
        if restored_baseline.get("feature_version") != feature_version:
            raise PromotionError("Backup feature and monitoring baseline versions do not match")
        if not model_backup_path.is_file():
            raise PromotionError("Backup model artifact is missing")
        validation = SkillModelService(model_path=model_backup_path, metadata_path=metadata_backup_path)
        if not validation.ready or validation.model_version != restored_version:
            raise PromotionError("Backup model files failed serving validation")

        backup_paths = self._backup_active_files(expected_current_version)
        replacements = [
            (model_backup_path, self.model_path),
            (metadata_backup_path, self.metadata_path),
            (baseline_backup_path, self.baseline_path),
        ]
        replaced: list[Path] = []
        try:
            for source, destination in replacements:
                staged = self._stage_copy(source, destination)
                os.replace(staged, destination)
                replaced.append(destination)
            restored_service = self._serving_reloader(expected_model_version=restored_version)
            if restored_service.model_version != restored_version or restored_service.feature_version != feature_version:
                raise PromotionError("Rolled-back serving versions do not match restored artifacts")
        except Exception as error:
            restore_errors = self._restore_active_files(backup_paths, replaced)
            try:
                self._serving_reloader(expected_model_version=expected_current_version)
            except Exception as reload_error:
                restore_errors.append(reload_error)
            if restore_errors:
                raise PromotionError("Rollback failed and active artifacts could not be restored") from error
            if isinstance(error, PromotionError):
                raise
            raise PromotionError("Rollback failed; the previous active model was restored") from error
        return {
            "model_version": restored_version,
            "feature_version": feature_version,
            "backup_files": [str(path) for path in backup_paths.values()],
        }

    def _backup_active_files(self, version: str) -> dict[str, Path]:
        if not self.model_path.is_file() or not self.metadata_path.is_file():
            raise PromotionError("Current model and metadata must both exist before promotion")
        suffix = 1
        while True:
            suffix_text = "" if suffix == 1 else f"_{suffix}"
            paths = {
                "model": self.backup_dir / f"skill_model_{version}{suffix_text}.joblib",
                "metadata": self.backup_dir / f"skill_metadata_{version}{suffix_text}.json",
            }
            if self.baseline_path.is_file():
                baseline = self._read_json(self.baseline_path)
                baseline_version = str(baseline.get("baseline_version", "baseline"))
                paths["baseline"] = self.backup_dir / f"monitoring_baseline_{baseline_version}{suffix_text}.json"
            if not any(path.exists() for path in paths.values()):
                break
            suffix += 1
        sources = {
            "model": self.model_path,
            "metadata": self.metadata_path,
            "baseline": self.baseline_path,
        }
        for key, target in paths.items():
            shutil.copy2(sources[key], target)
        return paths

    def _restore_active_files(self, backups: dict[str, Path], replaced: list[Path]) -> list[Exception]:
        destinations = {
            "model": self.model_path,
            "metadata": self.metadata_path,
            "baseline": self.baseline_path,
        }
        errors: list[Exception] = []
        for key, backup_path in backups.items():
            destination = destinations[key]
            if destination not in replaced:
                continue
            try:
                staged = self._stage_copy(backup_path, destination)
                os.replace(staged, destination)
            except Exception as error:
                errors.append(error)
        return errors

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PromotionError(f"Required metadata is unavailable: {path.name}") from error
        if not isinstance(value, dict):
            raise PromotionError(f"Metadata must be a JSON object: {path.name}")
        return value

    @staticmethod
    def _stage_copy(source: Path, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
        os.close(fd)
        staged = Path(name)
        try:
            shutil.copy2(source, staged)
        except Exception:
            staged.unlink(missing_ok=True)
            raise
        return staged

    @staticmethod
    def _write_json_stage(value: dict[str, Any], destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
        os.close(fd)
        staged = Path(name)
        try:
            staged.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        except Exception:
            staged.unlink(missing_ok=True)
            raise
        return staged
