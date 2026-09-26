from pydantic import BaseModel

from app.models.language import ProgrammingLanguage


class TopicSkillPrediction(BaseModel):
    topic: str
    predicted_skill: str | None = None
    confidence: float | None = None
    rule_based_skill: str | None = None
    status: str = "predicted"


class SkillProfileResponse(BaseModel):
    status: str
    message: str | None = None
    language: ProgrammingLanguage | None = None
    topics: list[TopicSkillPrediction] = []
