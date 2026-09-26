from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class GamificationProfileDocument:
    collection_name = "gamification_profiles"

    @staticmethod
    def new(*, user_id: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "user_id": user_id,
            "total_xp": 0,
            "level": 1,
            "current_streak": 0,
            "longest_streak": 0,
            "daily_goal_xp": 100,
            "daily_xp": 0,
            "last_activity_date": None,
            "created_at": now,
            "updated_at": now,
        }


class XPEventDocument:
    collection_name = "xp_events"

    @staticmethod
    def new(*, user_id: str, event_type: str, source_id: str, xp_amount: int) -> dict[str, Any]:
        return {
            "event_id": str(uuid4()),
            "user_id": user_id,
            "event_type": event_type,
            "source_id": source_id,
            "xp_amount": xp_amount,
            "created_at": datetime.now(timezone.utc),
        }


class BadgeDocument:
    collection_name = "badges"


class UserBadgeDocument:
    collection_name = "user_badges"
