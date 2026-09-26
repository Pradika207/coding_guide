"""Authenticated rule-based tutoring endpoints."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import PyMongoError

from app.database.config import settings
from app.schemas.tutor import TutorRequest, TutorResponse
from app.services.security import get_current_user
from app.services.tutor.tutor_service import (
    TutorQuestionAccessError,
    TutorQuestionNotFoundError,
    TutorQuestionStoreUnavailableError,
    TutorService,
    build_tutor_provider,
)
from app.services.tutor.tutor_service import TutorService

router = APIRouter(prefix="/tutor", tags=["AI Coding Tutor"])


@lru_cache(maxsize=1)
def get_tutor_service() -> TutorService:
    return TutorService(provider=build_tutor_provider(settings.tutor_provider))


def _provide_hint(
    request: TutorRequest,
    *,
    hint_level: int,
    tutor_service: TutorService,
) -> TutorResponse:
    try:
        return tutor_service.provide_hint(request, hint_level=hint_level)
    except TutorQuestionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found") from error
    except TutorQuestionAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except TutorQuestionStoreUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Question bank is unavailable") from error
    except (PyMongoError, RuntimeError) as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Tutor service is unavailable") from error


@router.post(
    "/hint",
    response_model=TutorResponse,
    summary="Get a progressive coding hint",
    description=(
        "Returns deterministic, educational guidance for a question and submission result. "
        "Requires authentication. The default provider is rule-based; source code is not stored or logged, "
        "and hidden evaluator data is never included."
    ),
)
def get_hint(
    request: TutorRequest,
    _current_user: dict = Depends(get_current_user),
    tutor_service: TutorService = Depends(get_tutor_service),
) -> TutorResponse:
    return _provide_hint(request, hint_level=request.hint_level, tutor_service=tutor_service)


@router.post(
    "/next-hint",
    response_model=TutorResponse,
    summary="Request the next progressive hint",
    description=(
        "Re-submit the same question/submission context to get the next hint level. "
        "Progression is stateless and deterministic; level 4 is the most detailed guidance, not executable code."
    ),
)
def get_next_hint(
    request: TutorRequest,
    _current_user: dict = Depends(get_current_user),
    tutor_service: TutorService = Depends(get_tutor_service),
) -> TutorResponse:
    next_level = request.hint_level + 1
    if next_level > settings.tutor_max_hint_level:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The maximum hint level has already been reached",
        )
    return _provide_hint(request, hint_level=next_level, tutor_service=tutor_service)
