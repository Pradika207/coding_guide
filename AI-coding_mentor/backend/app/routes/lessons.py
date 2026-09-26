from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import PyMongoError

from app.models.language import ProgrammingLanguage
from app.schemas.lesson import (
    CurrentLessonResponse,
    LessonProgressResponse,
    LessonPublic,
    LessonStartResponse,
    QuizPublic,
    TopicProgressResponse,
)
from app.schemas.lesson_quiz import QuizCompletionRequest, QuizCompletionResponse
from app.services import lessons as lesson_service
from app.services import roadmap as roadmap_service
from app.services.security import get_current_user

router = APIRouter(prefix="/lessons", tags=["lessons"])


def _database_error(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database is unavailable",
    )


def _lesson_error(error: lesson_service.LessonError) -> HTTPException:
    if isinstance(error, lesson_service.LessonNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, lesson_service.LessonAccessError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, lesson_service.LearningContentUnavailableError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if str(error) == "Unsupported topic":
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


@router.get("", response_model=list[LessonPublic])
def list_lessons(
    language: ProgrammingLanguage | None = Query(default=None),
    topic: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> list[LessonPublic]:
    try:
        normalized_topic = lesson_service.topic_from_filter(topic)
        lessons = lesson_service.list_lessons(
            user_id=current_user["user_id"],
            language=language,
            topic=normalized_topic,
        )
    except lesson_service.LessonError as error:
        raise _lesson_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return [LessonPublic.model_validate(lesson) for lesson in lessons]


@router.get("/current", response_model=CurrentLessonResponse)
def current_lesson(current_user: dict = Depends(get_current_user)) -> CurrentLessonResponse:
    try:
        lesson = lesson_service.current_lesson(user_id=current_user["user_id"])
    except lesson_service.LessonError as error:
        raise _lesson_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return CurrentLessonResponse.model_validate(lesson)


@router.get("/progress/{topic}", response_model=TopicProgressResponse)
def topic_progress(
    topic: str,
    current_user: dict = Depends(get_current_user),
) -> TopicProgressResponse:
    try:
        normalized_topic = lesson_service.topic_from_filter(topic)
        if normalized_topic is None:
            raise lesson_service.LessonError("Unsupported topic")
        roadmap = roadmap_service.get_roadmap(user_id=current_user["user_id"])
        language = ProgrammingLanguage(roadmap["language"])
        progress = lesson_service.topic_progress(
            user_id=current_user["user_id"],
            topic=normalized_topic,
            language=language,
        )
    except lesson_service.LessonError as error:
        raise _lesson_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return TopicProgressResponse.model_validate(progress)


@router.get("/{lesson_id}/quiz", response_model=QuizPublic)
def get_lesson_quiz(
    lesson_id: str,
    current_user: dict = Depends(get_current_user),
) -> QuizPublic:
    try:
        quiz = lesson_service.get_lesson_quiz(
            user_id=current_user["user_id"],
            lesson_id=lesson_id,
        )
    except lesson_service.LessonError as error:
        raise _lesson_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return QuizPublic.model_validate(quiz)


@router.post("/{lesson_id}/quiz/complete", response_model=QuizCompletionResponse)
def complete_lesson_quiz(
    lesson_id: str,
    request: QuizCompletionRequest,
    current_user: dict = Depends(get_current_user),
) -> QuizCompletionResponse:
    try:
        result = lesson_service.complete_lesson_quiz(
            user_id=current_user["user_id"],
            lesson_id=lesson_id,
            quiz_id=request.quiz_id,
            selected_option=request.selected_option,
        )
    except lesson_service.LessonError as error:
        raise _lesson_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return QuizCompletionResponse.model_validate(result)


@router.get("/{lesson_id}", response_model=LessonPublic)
def get_lesson(
    lesson_id: str,
    current_user: dict = Depends(get_current_user),
) -> LessonPublic:
    try:
        lesson = lesson_service.get_lesson(
            user_id=current_user["user_id"],
            lesson_id=lesson_id,
        )
    except lesson_service.LessonError as error:
        raise _lesson_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return LessonPublic.model_validate(lesson)


@router.post("/{lesson_id}/start", response_model=LessonStartResponse)
def start_lesson(
    lesson_id: str,
    current_user: dict = Depends(get_current_user),
) -> LessonStartResponse:
    try:
        lesson = lesson_service.get_lesson(
            user_id=current_user["user_id"],
            lesson_id=lesson_id,
        )
        progress = lesson_service.start_lesson(
            user_id=current_user["user_id"],
            lesson_id=lesson_id,
        )
    except lesson_service.LessonError as error:
        raise _lesson_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return LessonStartResponse(
        lesson=LessonPublic.model_validate(lesson),
        progress=LessonProgressResponse.model_validate(progress),
    )


@router.post("/{lesson_id}/complete", response_model=LessonProgressResponse)
def complete_lesson(
    lesson_id: str,
    current_user: dict = Depends(get_current_user),
) -> LessonProgressResponse:
    try:
        progress = lesson_service.complete_lesson(
            user_id=current_user["user_id"],
            lesson_id=lesson_id,
        )
    except lesson_service.LessonError as error:
        raise _lesson_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return LessonProgressResponse.model_validate(progress)
