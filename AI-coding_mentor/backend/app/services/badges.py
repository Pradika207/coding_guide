from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection

from app.database.mongodb import get_database
from app.models.gamification import BadgeDocument, UserBadgeDocument

BADGE_CATALOG = [
    {"badge_id": "first-step", "name": "First Step", "description": "Complete 1 lesson", "criteria_type": "lessons_completed", "criteria_value": 1, "icon": "footsteps"},
    {"badge_id": "quick-learner", "name": "Quick Learner", "description": "Complete 5 lessons", "criteria_type": "lessons_completed", "criteria_value": 5, "icon": "book"},
    {"badge_id": "dedicated-learner", "name": "Dedicated Learner", "description": "Complete 10 lessons", "criteria_type": "lessons_completed", "criteria_value": 10, "icon": "star"},
    {"badge_id": "week-warrior", "name": "Week Warrior", "description": "Maintain a 7-day streak", "criteria_type": "streak", "criteria_value": 7, "icon": "flame"},
    {"badge_id": "xp-starter", "name": "XP Starter", "description": "Reach 100 XP", "criteria_type": "xp", "criteria_value": 100, "icon": "spark"},
    {"badge_id": "xp-explorer", "name": "XP Explorer", "description": "Reach 500 XP", "criteria_type": "xp", "criteria_value": 500, "icon": "compass"},
    {"badge_id": "problem-solver", "name": "Problem Solver", "description": "Complete 5 coding problems", "criteria_type": "coding_completed", "criteria_value": 5, "icon": "code"},
    {"badge_id": "assessment-ready", "name": "Assessment Ready", "description": "Complete 1 coding assessment", "criteria_type": "assessments_completed", "criteria_value": 1, "icon": "check"},
]


def get_badges_collection() -> Collection:
    collection = get_database()[BadgeDocument.collection_name]
    collection.create_index("badge_id", unique=True)
    return collection


def get_user_badges_collection() -> Collection:
    collection = get_database()[UserBadgeDocument.collection_name]
    collection.create_index("user_id")
    collection.create_index([("user_id", 1), ("badge_id", 1)], unique=True)
    return collection


def _count_events(user_id: str, event_type: str) -> int:
    return get_database()["xp_events"].count_documents({"user_id": user_id, "event_type": event_type})


def evaluate_badges(*, user_id: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    badges = get_badges_collection()
    user_badges = get_user_badges_collection()
    for badge in BADGE_CATALOG:
        badges.update_one({"badge_id": badge["badge_id"]}, {"$setOnInsert": badge}, upsert=True)
    values = {
        "lessons_completed": _count_events(user_id, "lesson_completed"),
        "coding_completed": sum(_count_events(user_id, event) for event in ("coding_easy_completed", "coding_medium_completed", "coding_hard_completed")),
        "assessments_completed": _count_events(user_id, "assessment_completed"),
        "xp": profile["total_xp"],
        "streak": profile["longest_streak"],
    }
    new_badges = []
    for badge in BADGE_CATALOG:
        if values[badge["criteria_type"]] < badge["criteria_value"]:
            continue
        if user_badges.find_one({"user_id": user_id, "badge_id": badge["badge_id"]}):
            continue
        award = {"user_id": user_id, "badge_id": badge["badge_id"], "earned_at": datetime.now(timezone.utc)}
        user_badges.insert_one(award)
        new_badges.append({**badge, "earned_at": award["earned_at"]})
    return new_badges


def list_user_badges(*, user_id: str) -> list[dict[str, Any]]:
    user_badges = get_user_badges_collection()
    badges = get_badges_collection()
    output = []
    for earned in user_badges.find({"user_id": user_id}).sort("earned_at", -1):
        badge = badges.find_one({"badge_id": earned["badge_id"]})
        if badge:
            output.append({**badge, "earned_at": earned["earned_at"]})
    return output
