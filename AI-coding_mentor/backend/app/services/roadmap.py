from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection

from app.database.mongodb import get_database
from app.models.assessment_result import AssessmentResultDocument
from app.models.language import ProgrammingLanguage
from app.models.roadmap import (
    TOPIC_ORDER,
    LearningRoadmapDocument,
    RoadmapTopicStatus,
)
from app.services import assessment_results as result_service


class RoadmapError(RuntimeError):
    pass


class RoadmapNotFoundError(RoadmapError):
    pass


class AssessmentRequiredError(RoadmapError):
    pass


def get_roadmaps_collection() -> Collection:
    roadmaps = get_database()[LearningRoadmapDocument.collection_name]
    roadmaps.create_index("user_id")
    roadmaps.create_index([("user_id", 1), ("language", 1)], unique=True)
    roadmaps.create_index("source_assessment_id")
    return roadmaps


def _latest_result(user_id: str) -> dict[str, Any] | None:
    results = result_service.get_assessment_results_collection()
    return results.find_one({"user_id": user_id}, sort=[("created_at", -1)])


def _topic_statuses(result: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    topic_scores = result.get("topic_scores", {})
    completed_topics = {
        topic for topic, score in topic_scores.items() if score >= 80
    }
    recommended = result.get("recommended_next_topic")
    statuses: list[dict[str, Any]] = []
    for index, topic in enumerate(TOPIC_ORDER, start=1):
        topic_name = topic.display_name
        score = topic_scores.get(topic_name)
        if topic_name in completed_topics:
            topic_status = RoadmapTopicStatus.COMPLETED
        elif index == 1 or TOPIC_ORDER[index - 2].display_name in completed_topics:
            topic_status = RoadmapTopicStatus.UNLOCKED
        else:
            topic_status = RoadmapTopicStatus.LOCKED
        statuses.append(
            {
                "topic": topic_name,
                "order": index,
                "status": topic_status.value,
                "score": score,
            }
        )

    incomplete = [item for item in statuses if item["status"] != RoadmapTopicStatus.COMPLETED.value]
    recommended_item = next(
        (item for item in incomplete if item["topic"] == recommended),
        None,
    )
    if recommended_item is None:
        recommended_item = next(
            (item for item in incomplete if item["status"] != RoadmapTopicStatus.LOCKED.value),
            incomplete[0] if incomplete else None,
        )
    if recommended_item is None:
        raise RoadmapError("Roadmap has no incomplete topics")

    recommended_item["status"] = RoadmapTopicStatus.RECOMMENDED.value
    return statuses, recommended_item["topic"]


def _to_public(roadmap: dict[str, Any]) -> dict[str, Any]:
    return roadmap


def generate_roadmap(*, user_id: str) -> dict[str, Any]:
    result = _latest_result(user_id)
    if result is None:
        raise AssessmentRequiredError("Complete an assessment before generating a roadmap.")

    language = ProgrammingLanguage(result["language"])
    topics, current_topic = _topic_statuses(result)
    roadmaps = get_roadmaps_collection()
    existing = roadmaps.find_one({"user_id": user_id, "language": language.value})
    now = datetime.now(timezone.utc)
    if existing is None:
        roadmap = LearningRoadmapDocument.new(
            user_id=user_id,
            language=language,
            source_assessment_id=result["session_id"],
            topics=topics,
            current_topic=current_topic,
        )
        roadmaps.insert_one(roadmap)
        return _to_public(roadmap)

    if existing.get("source_assessment_id") == result["session_id"]:
        return _to_public(existing)

    roadmaps.update_one(
        {"roadmap_id": existing["roadmap_id"], "user_id": user_id},
        {
            "$set": {
                "source_assessment_id": result["session_id"],
                "topics": topics,
                "current_topic": current_topic,
                "updated_at": now,
            }
        },
    )
    existing.update(
        {
            "source_assessment_id": result["session_id"],
            "topics": topics,
            "current_topic": current_topic,
            "updated_at": now,
        }
    )
    return _to_public(existing)


def get_roadmap(*, user_id: str) -> dict[str, Any]:
    roadmap = get_roadmaps_collection().find_one({"user_id": user_id})
    if roadmap is None:
        raise RoadmapNotFoundError("No learning roadmap has been generated")
    return _to_public(roadmap)


def get_current_topic(*, user_id: str) -> dict[str, Any]:
    roadmap = get_roadmap(user_id=user_id)
    current_topic = next(
        item for item in roadmap["topics"] if item["topic"] == roadmap["current_topic"]
    )
    return {
        "topic": current_topic["topic"],
        "status": current_topic["status"],
        "reason": "This is currently your weakest assessed topic.",
    }
