from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.language import ProgrammingLanguage
from app.models.question import Topic


class SkillPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: ProgrammingLanguage
    topic: Topic
    assessment_accuracy: float = Field(ge=0, le=100, allow_inf_nan=False, description="Assessment percentage from 0 to 100")
    easy_success_rate: float = Field(ge=0, le=1, allow_inf_nan=False, description="Rate from 0 to 1")
    medium_success_rate: float = Field(ge=0, le=1, allow_inf_nan=False, description="Rate from 0 to 1")
    hard_success_rate: float = Field(ge=0, le=1, allow_inf_nan=False, description="Rate from 0 to 1")
    overall_success_rate: float = Field(ge=0, le=1, allow_inf_nan=False, description="Rate from 0 to 1")
    failure_rate: float = Field(ge=0, le=1, allow_inf_nan=False, description="Rate from 0 to 1")
    recent_success_rate: float = Field(ge=0, le=1, allow_inf_nan=False, description="Rate from 0 to 1")
    lesson_completion_rate: float = Field(ge=0, le=1, allow_inf_nan=False, description="Rate from 0 to 1")
    attempt_count: int = Field(ge=0)
    topic_count: int = Field(
        ge=0,
        description="Validated context; not a feature in the currently trained model.",
    )


class SkillPredictionResponse(BaseModel):
    prediction: Literal["beginner", "intermediate", "advanced"]
    model_version: str
    feature_version: str
    model_status: Literal["ready"]


class SkillModelHealthResponse(BaseModel):
    status: Literal["healthy", "unavailable"]
    model_status: Literal["ready", "unavailable"]
    model_version: str | None = None
    feature_version: str | None = None