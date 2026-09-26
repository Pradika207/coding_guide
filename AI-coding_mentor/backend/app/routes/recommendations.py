from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import PyMongoError

from app.schemas.recommendation import RecommendationResponse
from app.services import recommendations
from app.services.security import get_current_user

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _database_error(error: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable")


def _recommendation_error(error: recommendations.RecommendationError) -> HTTPException:
    if isinstance(error, recommendations.AssessmentRequiredError):
        return HTTPException(status_code=status.HTTP_200_OK, detail=str(error))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


def _language(current_user: dict):
    selected = current_user.get("selected_language")
    if not selected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select a programming language before requesting recommendations")
    from app.models.language import ProgrammingLanguage
    try:
        return ProgrammingLanguage(selected)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User language is not supported") from error


@router.get("", response_model=RecommendationResponse)
def get_recommendations(limit: int = Query(default=5, ge=1, le=20), current_user: dict = Depends(get_current_user)) -> RecommendationResponse:
    try:
        response = recommendations.get_current_recommendations(user_id=current_user["user_id"], language=_language(current_user), limit=limit)
    except recommendations.RecommendationError as error:
        if isinstance(error, recommendations.AssessmentRequiredError):
            return RecommendationResponse(status="assessment_required", message=str(error), recommendations=[])
        raise _recommendation_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return RecommendationResponse.model_validate(response)


@router.post("/refresh", response_model=RecommendationResponse)
def refresh_recommendations(limit: int = Query(default=5, ge=1, le=20), current_user: dict = Depends(get_current_user)) -> RecommendationResponse:
    try:
        response = recommendations.generate_recommendations(user_id=current_user["user_id"], language=_language(current_user), limit=limit)
    except recommendations.RecommendationError as error:
        if isinstance(error, recommendations.AssessmentRequiredError):
            return RecommendationResponse(status="assessment_required", message=str(error), recommendations=[])
        raise _recommendation_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return RecommendationResponse.model_validate(response)


@router.get("/current", response_model=RecommendationResponse)
def current_recommendations(limit: int = Query(default=5, ge=1, le=20), current_user: dict = Depends(get_current_user)) -> RecommendationResponse:
    return get_recommendations(limit=limit, current_user=current_user)
