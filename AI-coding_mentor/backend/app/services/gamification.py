from datetime import date, datetime, timedelta, timezone
from math import floor, sqrt
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from app.database.mongodb import get_database
from app.models.gamification import GamificationProfileDocument, XPEventDocument

XP_REWARDS = {
    "lesson_completed": 10,
    "quiz_completed": 20,
    "coding_easy_completed": 20,
    "coding_medium_completed": 40,
    "coding_hard_completed": 70,
    "assessment_completed": 100,
}


def calculate_level(total_xp: int) -> int:
    return floor(sqrt(total_xp / 100)) + 1


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def get_profiles_collection() -> Collection:
    collection = get_database()[GamificationProfileDocument.collection_name]
    collection.create_index("user_id", unique=True)
    return collection


def get_xp_events_collection() -> Collection:
    collection = get_database()[XPEventDocument.collection_name]
    collection.create_index("user_id")
    collection.create_index("created_at")
    collection.create_index([("user_id", 1), ("event_type", 1), ("source_id", 1)], unique=True)
    return collection


def get_or_create_profile(*, user_id: str) -> dict[str, Any]:
    profiles = get_profiles_collection()
    profile = profiles.find_one({"user_id": user_id})
    if profile is not None:
        return profile
    profile = GamificationProfileDocument.new(user_id=user_id)
    try:
        profiles.insert_one(profile)
    except DuplicateKeyError:
        profile = profiles.find_one({"user_id": user_id})
    return profile


def _update_activity(profile: dict[str, Any], *, xp_amount: int) -> None:
    today = utc_today()
    last = profile.get("last_activity_date")
    if isinstance(last, datetime):
        last = last.date()
    if isinstance(last, str):
        last = date.fromisoformat(last)
    if last == today:
        streak = profile["current_streak"]
        daily_xp = profile.get("daily_xp", 0)
    elif last == today - timedelta(days=1):
        streak = profile["current_streak"] + 1
        daily_xp = 0
    else:
        streak = 1
        daily_xp = 0
    profile["current_streak"] = streak
    profile["longest_streak"] = max(profile["longest_streak"], streak)
    profile["last_activity_date"] = today.isoformat()
    profile["daily_xp"] = daily_xp + xp_amount
    profile["total_xp"] += xp_amount
    profile["level"] = calculate_level(profile["total_xp"])
    profile["updated_at"] = datetime.now(timezone.utc)


def record_activity(*, user_id: str, event_type: str, source_id: str) -> dict[str, Any]:
    if event_type not in XP_REWARDS:
        raise ValueError("Unsupported XP event type")
    events = get_xp_events_collection()
    existing = events.find_one({"user_id": user_id, "event_type": event_type, "source_id": source_id})
    profile = get_or_create_profile(user_id=user_id)
    if existing is not None:
        return {"profile": profile, "event": existing, "awarded": False}
    event = XPEventDocument.new(
        user_id=user_id,
        event_type=event_type,
        source_id=source_id,
        xp_amount=XP_REWARDS[event_type],
    )
    try:
        events.insert_one(event)
    except DuplicateKeyError:
        existing = events.find_one({"user_id": user_id, "event_type": event_type, "source_id": source_id})
        return {"profile": profile, "event": existing, "awarded": False}
    _update_activity(profile, xp_amount=event["xp_amount"])
    get_profiles_collection().update_one(
        {"user_id": user_id},
        {"$set": {key: profile[key] for key in profile if key != "_id"}},
    )
    return {"profile": profile, "event": event, "awarded": True}


def set_daily_goal(*, user_id: str, daily_goal_xp: int) -> dict[str, Any]:
    profile = get_or_create_profile(user_id=user_id)
    profile["daily_goal_xp"] = daily_goal_xp
    profile["updated_at"] = datetime.now(timezone.utc)
    get_profiles_collection().update_one({"user_id": user_id}, {"$set": {"daily_goal_xp": daily_goal_xp, "updated_at": profile["updated_at"]}})
    return profile


def summary(profile: dict[str, Any]) -> dict[str, Any]:
    goal = profile["daily_goal_xp"]
    daily_xp = profile.get("daily_xp", 0)
    return {
        **{key: profile[key] for key in ("total_xp", "level", "current_streak", "longest_streak", "daily_goal_xp", "daily_xp")},
        "daily_goal_progress": min(daily_xp / goal, 1) if goal else 0,
        "daily_goal_completed": daily_xp >= goal,
    }


def xp_history(*, user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    return list(get_xp_events_collection().find({"user_id": user_id}).sort("created_at", -1).skip(offset).limit(limit))
