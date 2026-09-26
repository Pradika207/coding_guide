from datetime import datetime

from pydantic import BaseModel, Field


class GamificationSummary(BaseModel):
    total_xp: int
    level: int
    current_streak: int
    longest_streak: int
    daily_goal_xp: int
    daily_xp: int
    daily_goal_progress: float
    daily_goal_completed: bool


class DailyGoalRequest(BaseModel):
    daily_goal_xp: int = Field(ge=10, le=1000)


class BadgeResponse(BaseModel):
    badge_id: str
    name: str
    description: str
    criteria_type: str
    criteria_value: int
    icon: str
    earned_at: datetime


class XPEventResponse(BaseModel):
    event_id: str
    event_type: str
    source_id: str
    xp_amount: int
    created_at: datetime
