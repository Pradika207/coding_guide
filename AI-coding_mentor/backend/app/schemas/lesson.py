from datetime import datetime

from pydantic import BaseModel

from app.models.lesson import ContentType, LessonProgressStatus
from app.models.language import ProgrammingLanguage


class LessonContentItem(BaseModel):
    type: ContentType
    title: str
    text: str


class LessonPublic(BaseModel):
    lesson_id: str
    language: ProgrammingLanguage
    topic: str
    title: str
    description: str
    order: int
    content: list[LessonContentItem]
    question_ids: list[str]


class LessonProgressResponse(BaseModel):
    progress_id: str
    lesson_id: str
    status: LessonProgressStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None


class LessonStartResponse(BaseModel):
    lesson: LessonPublic
    progress: LessonProgressResponse


class CurrentLessonResponse(BaseModel):
    lesson_id: str
    topic: str
    title: str
    progress: int
    status: str


class TopicProgressResponse(BaseModel):
    topic: str
    total_lessons: int
    completed_lessons: int
    progress_percent: int


class QuizPublic(BaseModel):
    quiz_id: str
    question: str
    options: list[str]
