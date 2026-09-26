from datetime import datetime

from pydantic import BaseModel, Field

from app.models.language import ProgrammingLanguage
from app.models.question import Difficulty, Topic


class TestCase(BaseModel):
    input: str = Field(min_length=1, max_length=10000)
    expected_output: str = Field(min_length=1, max_length=10000)
    is_hidden: bool = False


class QuestionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    language: ProgrammingLanguage
    topic: Topic
    difficulty: Difficulty
    sample_input: str = Field(min_length=1, max_length=10000)
    sample_output: str = Field(min_length=1, max_length=10000)
    test_cases: list[TestCase] = Field(min_length=1, max_length=100)
    constraints: list[str] = Field(min_length=1, max_length=50)
    time_limit: int = Field(gt=0, le=60)
    memory_limit: int = Field(gt=0, le=4096)


class QuestionPublic(BaseModel):
    question_id: str
    title: str
    description: str
    language: ProgrammingLanguage
    topic: Topic
    difficulty: Difficulty
    sample_input: str
    sample_output: str
    constraints: list[str]
    time_limit: int
    memory_limit: int
    created_at: datetime


class QuestionListResponse(BaseModel):
    questions: list[QuestionPublic]
