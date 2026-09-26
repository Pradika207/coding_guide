"""Deterministic increments for existing model and monitoring-baseline versions."""

from __future__ import annotations

import re


_MODEL_VERSION_PATTERN = re.compile(r"^skill-model-v(\d+)$")
_BASELINE_VERSION_PATTERN = re.compile(r"^baseline-v(\d+)$")


def next_model_version(current_version: str) -> str:
    match = _MODEL_VERSION_PATTERN.fullmatch(current_version)
    if match is None:
        raise ValueError(f"Unsupported model version format: {current_version!r}")
    return f"skill-model-v{int(match.group(1)) + 1}"


def next_baseline_version(current_version: str | None) -> str:
    if current_version is None:
        return "baseline-v1"
    match = _BASELINE_VERSION_PATTERN.fullmatch(current_version)
    if match is None:
        raise ValueError(f"Unsupported baseline version format: {current_version!r}")
    return f"baseline-v{int(match.group(1)) + 1}"
