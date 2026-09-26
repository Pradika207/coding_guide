from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.models.language import ProgrammingLanguage
from app.models.question import Topic


class ContentType(str, Enum):
    CONCEPT = "concept"
    EXAMPLE = "example"
    TIP = "tip"
    WARNING = "warning"
    SUMMARY = "summary"


class LessonProgressStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class LessonDocument:
    collection_name = "lessons"

    @staticmethod
    def new(
        *,
        language: ProgrammingLanguage,
        topic: Topic,
        title: str,
        description: str,
        order: int,
        content: list[dict[str, str]],
        quiz_ids: list[str],
        question_ids: list[str],
        lesson_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "lesson_id": lesson_id or str(uuid4()),
            "language": language.value,
            "topic": topic.value,
            "title": title,
            "description": description,
            "order": order,
            "content": content,
            "quiz_ids": quiz_ids,
            "question_ids": question_ids,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def to_public(document: dict[str, Any]) -> dict[str, Any]:
        return {
            "lesson_id": document["lesson_id"],
            "language": document["language"],
            "topic": Topic(document["topic"]).display_name,
            "title": document["title"],
            "description": document["description"],
            "order": document["order"],
            "content": document["content"],
            "question_ids": document.get("question_ids", []),
        }


class LessonProgressDocument:
    collection_name = "lesson_progress"

    @staticmethod
    def new(*, user_id: str, lesson_id: str) -> dict[str, Any]:
        return {
            "progress_id": str(uuid4()),
            "user_id": user_id,
            "lesson_id": lesson_id,
            "status": LessonProgressStatus.IN_PROGRESS.value,
            "started_at": datetime.now(timezone.utc),
            "completed_at": None,
        }


class QuizDocument:
    collection_name = "lesson_quizzes"

    @staticmethod
    def new(
        *,
        lesson_id: str,
        question: str,
        options: list[str],
        correct_option: str,
        explanation: str,
        quiz_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "quiz_id": quiz_id or str(uuid4()),
            "lesson_id": lesson_id,
            "question": question,
            "options": options,
            "correct_option": correct_option,
            "explanation": explanation,
        }

    @staticmethod
    def to_public(document: dict[str, Any]) -> dict[str, Any]:
        return {
            "quiz_id": document["quiz_id"],
            "question": document["question"],
            "options": document["options"],
        }
