from datetime import datetime

from pydantic import BaseModel

from app.models.assessment_result import SkillLevel
from app.models.language import ProgrammingLanguage


class AssessmentResultResponse(BaseModel):
    result_id: str
    session_id: str
    language: ProgrammingLanguage
    overall_score: int
    accuracy: int
    skill_level: SkillLevel
    topic_scores: dict[str, int]
    strong_topics: list[str]
    weak_topics: list[str]
    recommended_next_topic: str | None
    created_at: datetime


class AssessmentHistoryItem(BaseModel):
    session_id: str
    language: ProgrammingLanguage
    score: int
    skill_level: SkillLevel
    created_at: datetime
