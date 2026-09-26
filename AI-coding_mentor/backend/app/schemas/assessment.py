from datetime import datetime

from pydantic import BaseModel, Field

from app.database.config import settings
from app.models.language import ProgrammingLanguage
from app.models.question import Difficulty, Topic


class AssessmentQuestion(BaseModel):
    question_id: str
    title: str
    description: str
    topic: Topic
    difficulty: Difficulty
    sample_input: str
    sample_output: str
    constraints: list[str]


class AssessmentStartResponse(BaseModel):
    session_id: str
    language: ProgrammingLanguage
    status: str
    questions: list[AssessmentQuestion]


class AssessmentSubmissionRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=200)
    source_code: str = Field(min_length=1, max_length=settings.max_source_code_bytes)
    stdin: str = Field(default="", max_length=settings.max_stdin_bytes)


class AssessmentSubmissionResponse(BaseModel):
    question_id: str
    status: str
    stdout: str
    stderr: str
    compile_output: str
    execution_time: float | None = None
    memory: int | None = None
    attempt_number: int


class AssessmentSummary(BaseModel):
    session_id: str
    status: str
    score: int
    total_questions: int
    solved_questions: int
    accuracy: int
    language: ProgrammingLanguage


class AssessmentSessionRecord(BaseModel):
    session_id: str
    language: ProgrammingLanguage
    status: str
    score: int | None
    started_at: datetime
    completed_at: datetime | None
