from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.models.language import ProgrammingLanguage
from app.models.question import Topic


class RoadmapTopicStatus(str, Enum):
    COMPLETED = "completed"
    UNLOCKED = "unlocked"
    LOCKED = "locked"
    RECOMMENDED = "recommended"


TOPIC_ORDER: tuple[Topic, ...] = (
    Topic.FUNDAMENTALS,
    Topic.VARIABLES,
    Topic.CONDITIONALS,
    Topic.LOOPS,
    Topic.FUNCTIONS,
    Topic.ARRAYS,
    Topic.STRINGS,
    Topic.SEARCHING,
    Topic.SORTING,
    Topic.RECURSION,
    Topic.LINKED_LISTS,
    Topic.STACK,
    Topic.QUEUE,
    Topic.HASHING,
    Topic.TREES,
    Topic.GRAPHS,
    Topic.DYNAMIC_PROGRAMMING,
    Topic.OBJECT_ORIENTED_PROGRAMMING,
)


class LearningRoadmapDocument:
    collection_name = "learning_roadmaps"

    @staticmethod
    def new(
        *,
        user_id: str,
        language: ProgrammingLanguage,
        source_assessment_id: str,
        topics: list[dict[str, Any]],
        current_topic: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "roadmap_id": str(uuid4()),
            "user_id": user_id,
            "language": language.value,
            "source_assessment_id": source_assessment_id,
            "topics": topics,
            "current_topic": current_topic,
            "created_at": now,
            "updated_at": now,
        }
