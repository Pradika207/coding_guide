from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.models.language import ProgrammingLanguage


class SkillLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class AssessmentResultDocument:
    collection_name = "assessment_results"

    @staticmethod
    def new(
        *,
        session_id: str,
        user_id: str,
        language: ProgrammingLanguage,
        overall_score: int,
        topic_scores: dict[str, int],
        skill_level: SkillLevel,
        strong_topics: list[str],
        weak_topics: list[str],
        recommended_next_topic: str | None,
    ) -> dict[str, Any]:
        return {
            "result_id": str(uuid4()),
            "session_id": session_id,
            "user_id": user_id,
            "language": language.value,
            "overall_score": overall_score,
            "accuracy": overall_score,
            "skill_level": skill_level.value,
            "topic_scores": topic_scores,
            "strong_topics": strong_topics,
            "weak_topics": weak_topics,
            "recommended_next_topic": recommended_next_topic,
            "created_at": datetime.now(timezone.utc),
        }
