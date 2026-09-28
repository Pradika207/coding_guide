from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import PyMongoError

from app.models.language import ProgrammingLanguage
from app.schemas.assessment import (
    AssessmentQuestion,
    AssessmentStartResponse,
    AssessmentSubmissionRequest,
    AssessmentSubmissionResponse,
    AssessmentSummary,
)
from app.schemas.assessment_result import AssessmentHistoryItem, AssessmentResultResponse
from app.services import assessment as assessment_service
from app.services import assessment_results as result_service
from app.services import submissions as submission_service
from app.services import judge0
from app.services.security import get_current_user

router = APIRouter(prefix="/assessment", tags=["assessment"])


def _database_error(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database is unavailable",
    )


def _assessment_error(error: assessment_service.AssessmentError) -> HTTPException:
    if isinstance(error, assessment_service.AssessmentNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, assessment_service.AssessmentQuestionError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.post("/start", response_model=AssessmentStartResponse)
def start_assessment(current_user: dict = Depends(get_current_user)) -> AssessmentStartResponse:
    selected_language = current_user.get("selected_language")
    if selected_language is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select a programming language before starting an assessment",
        )

    try:
        language = ProgrammingLanguage(selected_language)
        result = assessment_service.start_assessment(
            user_id=current_user["user_id"],
            language=language,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User language is not supported",
        ) from error
    except assessment_service.AssessmentError as error:
        raise _assessment_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)

    session = result["session"]
    return AssessmentStartResponse(
        session_id=session["session_id"],
        language=language,
        status=session["status"],
        questions=[
            AssessmentQuestion.model_validate(question)
            for question in result["questions"]
        ],
    )


@router.post(
    "/{session_id}/submit",
    response_model=AssessmentSubmissionResponse,
)
def submit_assessment_code(
    session_id: str,
    request: AssessmentSubmissionRequest,
    current_user: dict = Depends(get_current_user),
) -> AssessmentSubmissionResponse:
    try:
        result = submission_service.submit_assessment_code(
            session_id=session_id,
            user_id=current_user["user_id"],
            question_id=request.question_id,
            source_code=request.source_code,
            stdin=request.stdin,
        )
    except assessment_service.AssessmentError as error:
        raise _assessment_error(error)
    except judge0.Judge0ConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Code execution service is not configured",
        ) from error
    except judge0.Judge0TimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Code execution timed out",
        ) from error
    except judge0.Judge0RequestError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Code execution service is unavailable",
        ) from error
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)

    return AssessmentSubmissionResponse.model_validate(result)


@router.post("/{session_id}/complete", response_model=AssessmentSummary)
def complete_assessment(
    session_id: str,
    current_user: dict = Depends(get_current_user),
) -> AssessmentSummary:
    try:
        result = assessment_service.complete_assessment(
            session_id=session_id,
            user_id=current_user["user_id"],
        )
    except assessment_service.AssessmentError as error:
        raise _assessment_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)

    return AssessmentSummary.model_validate(result)


@router.get("/history", response_model=list[AssessmentHistoryItem])
def assessment_history(
    current_user: dict = Depends(get_current_user),
) -> list[AssessmentHistoryItem]:
    try:
        results = result_service.get_history(user_id=current_user["user_id"])
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return [
        AssessmentHistoryItem(
            session_id=result["session_id"],
            language=result["language"],
            score=result["overall_score"],
            skill_level=result["skill_level"],
            created_at=result["created_at"],
        )
        for result in results
    ]


@router.get("/{session_id}/result", response_model=AssessmentResultResponse)
def assessment_result(
    session_id: str,
    current_user: dict = Depends(get_current_user),
) -> AssessmentResultResponse:
    try:
        result = result_service.get_or_create_result(
            session_id=session_id,
            user_id=current_user["user_id"],
        )
    except assessment_service.AssessmentError as error:
        raise _assessment_error(error)
    except result_service.AssessmentReportError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return AssessmentResultResponse.model_validate(result)
