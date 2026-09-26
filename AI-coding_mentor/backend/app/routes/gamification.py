from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import PyMongoError

from app.schemas.gamification import BadgeResponse, DailyGoalRequest, GamificationSummary, XPEventResponse
from app.services import badges, gamification
from app.services.security import get_current_user

router = APIRouter(prefix="/gamification", tags=["gamification"])


def _database_error(error: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable")


@router.get("", response_model=GamificationSummary)
def get_gamification(current_user: dict = Depends(get_current_user)) -> GamificationSummary:
    try:
        profile = gamification.get_or_create_profile(user_id=current_user["user_id"])
        return GamificationSummary.model_validate(gamification.summary(profile))
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)


@router.put("/daily-goal", response_model=GamificationSummary)
def update_daily_goal(request: DailyGoalRequest, current_user: dict = Depends(get_current_user)) -> GamificationSummary:
    try:
        profile = gamification.set_daily_goal(user_id=current_user["user_id"], daily_goal_xp=request.daily_goal_xp)
        return GamificationSummary.model_validate(gamification.summary(profile))
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)


@router.get("/badges", response_model=list[BadgeResponse])
def get_badges(current_user: dict = Depends(get_current_user)) -> list[BadgeResponse]:
    try:
        return [BadgeResponse.model_validate(item) for item in badges.list_user_badges(user_id=current_user["user_id"])]
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)


@router.get("/xp-history", response_model=list[XPEventResponse])
def get_xp_history(limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), current_user: dict = Depends(get_current_user)) -> list[XPEventResponse]:
    try:
        events = gamification.xp_history(user_id=current_user["user_id"], limit=limit, offset=offset)
        return [XPEventResponse.model_validate(item) for item in events]
    except (PyMongoError, RuntimeError) as error:
        raise _database_error(error)
