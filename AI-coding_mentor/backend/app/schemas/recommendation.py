from datetime import datetime

from pydantic import BaseModel

from app.models.language import ProgrammingLanguage


class RecommendationItem(BaseModel):
    recommendation_id: str
    question_id: str
    title: str
    topic: str
    difficulty: str
    score: int
    reason: str


class RecommendationResponse(BaseModel):
    status: str
    message: str | None = None
    language: ProgrammingLanguage | None = None
    recommendations: list[RecommendationItem] = []
    generated_at: datetime | None = None
