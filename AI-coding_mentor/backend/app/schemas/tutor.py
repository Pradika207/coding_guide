from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.database.config import settings
from app.models.language import ProgrammingLanguage
from app.models.question import Difficulty, Topic

SubmissionStatus = Literal[
    "accepted",
    "wrong_answer",
    "compilation_error",
    "runtime_error",
    "time_limit_exceeded",
    "memory_limit_exceeded",
    "pending",
    "processing",
    "internal_error",
]


class TutorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    question_id: str = Field(min_length=1, max_length=200)
    language: ProgrammingLanguage
    code: str = Field(min_length=1, max_length=settings.tutor_max_code_length)
    submission_status: SubmissionStatus
    compiler_error: str | None = Field(default=None, max_length=4000)
    runtime_error: str | None = Field(default=None, max_length=4000)
    topic: Topic
    difficulty: Difficulty
    hint_level: int = Field(default=1, ge=1, le=settings.tutor_max_hint_level)


class TutorResponse(BaseModel):
    hint: str
    explanation: str
    concept: str
    next_step: str
    hint_level: int = Field(ge=1, le=4)
    provider: str
    can_request_next_hint: bool
