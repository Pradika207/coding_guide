from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import PyMongoError

from app.schemas.roadmap import CurrentRoadmapTopicResponse, RoadmapResponse
from app.services import roadmap as roadmap_service
from app.services.security import get_current_user

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


def _database_error(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database is unavailable",
    )


def _roadmap_error(error: roadmap_service.RoadmapError) -> HTTPException:
    if isinstance(error, roadmap_service.AssessmentRequiredError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    if isinstance(error, roadmap_service.RoadmapNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


@router.post("/generate", response_model=RoadmapResponse)
def generate_roadmap(current_user: dict = Depends(get_current_user)) -> RoadmapResponse:
    try:
        roadmap = roadmap_service.generate_roadmap(user_id=current_user["user_id"])
    except roadmap_service.RoadmapError as error:
        raise _roadmap_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return RoadmapResponse.model_validate(roadmap)


@router.get("/current", response_model=CurrentRoadmapTopicResponse)
def current_roadmap_topic(
    current_user: dict = Depends(get_current_user),
) -> CurrentRoadmapTopicResponse:
    try:
        current_topic = roadmap_service.get_current_topic(user_id=current_user["user_id"])
    except roadmap_service.RoadmapError as error:
        raise _roadmap_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return CurrentRoadmapTopicResponse.model_validate(current_topic)


@router.get("", response_model=RoadmapResponse)
def get_current_roadmap(current_user: dict = Depends(get_current_user)) -> RoadmapResponse:
    try:
        roadmap = roadmap_service.get_roadmap(user_id=current_user["user_id"])
    except roadmap_service.RoadmapError as error:
        raise _roadmap_error(error)
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
    return RoadmapResponse.model_validate(roadmap)
