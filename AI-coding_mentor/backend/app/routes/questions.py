from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import PyMongoError

from app.models.language import ProgrammingLanguage
from app.models.question import Difficulty, Topic
from app.schemas.question import QuestionCreate, QuestionListResponse, QuestionPublic
from app.services.questions import (
    create_question,
    find_question,
    find_questions,
)
from app.services.security import get_current_user

router = APIRouter(prefix="/questions", tags=["questions"])


def _database_error(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database is unavailable",
    )


@router.post("", response_model=QuestionPublic, status_code=status.HTTP_201_CREATED)
def add_question(request: QuestionCreate, _: dict = Depends(get_current_user)) -> QuestionPublic:
    try:
        question = create_question(request)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return QuestionPublic.model_validate(question)


@router.get("", response_model=QuestionListResponse)
def list_question_bank(
    language: ProgrammingLanguage | None = Query(default=None),
    topic: Topic | None = Query(default=None),
    difficulty: Difficulty | None = Query(default=None),
) -> QuestionListResponse:
    try:
        questions = find_questions(
            language=language,
            topic=topic,
            difficulty=difficulty,
        )
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return QuestionListResponse(
        questions=[QuestionPublic.model_validate(question) for question in questions]
    )


@router.get("/{question_id}", response_model=QuestionPublic)
def get_question(question_id: str) -> QuestionPublic:
    try:
        question = find_question(question_id)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )
    return QuestionPublic.model_validate(question)
