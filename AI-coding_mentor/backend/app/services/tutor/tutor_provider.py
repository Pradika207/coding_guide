"""Provider interface for safe, hint-oriented coding assistance."""

from __future__ import annotations

from typing import Any, Protocol

from app.schemas.tutor import TutorRequest, TutorResponse


class TutorProvider(Protocol):
    name: str

    def provide_hint(
        self,
        request: TutorRequest,
        *,
        hint_level: int | None = None,
        question_context: dict[str, Any] | None = None,
    ) -> TutorResponse:
        """Return a progressive tutoring response without exposing hidden tests."""
