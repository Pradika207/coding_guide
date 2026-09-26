from datetime import datetime

from pydantic import BaseModel

from app.models.language import ProgrammingLanguage
from app.models.roadmap import RoadmapTopicStatus


class RoadmapTopic(BaseModel):
    topic: str
    order: int
    status: RoadmapTopicStatus
    score: int | None = None


class RoadmapResponse(BaseModel):
    roadmap_id: str
    user_id: str
    language: ProgrammingLanguage
    source_assessment_id: str
    current_topic: str
    topics: list[RoadmapTopic]
    created_at: datetime
    updated_at: datetime


class CurrentRoadmapTopicResponse(BaseModel):
    topic: str
    status: RoadmapTopicStatus
    reason: str
