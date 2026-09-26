from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.models.language import ProgrammingLanguage


class AssessmentStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class AssessmentSessionDocument:
    collection_name = "assessment_sessions"

    @staticmethod
    def new(
        *,
        user_id: str,
        language: ProgrammingLanguage,
        question_ids: list[str],
        question_metadata: list[dict[str, str]],
    ) -> dict[str, Any]:
        return {
            "session_id": str(uuid4()),
            "user_id": user_id,
            "language": language.value,
            "question_ids": question_ids,
            "question_metadata": question_metadata,
            "started_at": datetime.now(timezone.utc),
            "completed_at": None,
            "status": AssessmentStatus.IN_PROGRESS.value,
            "score": None,
        }


class AssessmentSubmissionDocument:
    collection_name = "assessment_submissions"

    @staticmethod
    def new(
        *,
        session_id: str,
        user_id: str,
        question_id: str,
        source_code: str,
        stdin: str,
        status: str,
        attempt_number: int,
        execution_time: float | None,
        memory: int | None,
    ) -> dict[str, Any]:
        return {
            "submission_id": str(uuid4()),
            "session_id": session_id,
            "user_id": user_id,
            "question_id": question_id,
            "source_code": source_code,
            "stdin": stdin,
            "status": status,
            "attempt_number": attempt_number,
            "submitted_at": datetime.now(timezone.utc),
            "execution_time": execution_time,
            "memory": memory,
        }
