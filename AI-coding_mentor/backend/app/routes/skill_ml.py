from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from app.models.language import ProgrammingLanguage
from app.schemas.ml_prediction import (
    SkillModelHealthResponse,
    SkillPredictionRequest,
    SkillPredictionResponse,
)
from app.schemas.skill_ml import SkillProfileResponse, TopicSkillPrediction
from app.services import skill_prediction
from app.services.security import get_current_user
from ml.features.skill_features import build_feature_row_from_rates
from ml.monitoring.monitoring_service import MonitoringService, get_monitoring_service
from ml.monitoring.prediction_logger import log_prediction
from ml.serving.skill_model_service import (
    SkillModelService,
    SkillModelUnavailableError,
    SkillPredictionFailure,
    get_skill_model_service,
)

router = APIRouter(prefix="/ml", tags=["machine learning"])


@router.get("/skill-profile", response_model=SkillProfileResponse)
def skill_profile(current_user: dict = Depends(get_current_user)) -> SkillProfileResponse:
    selected_language = current_user.get("selected_language")
    if not selected_language:
        return SkillProfileResponse(status="insufficient_data", message="Select a programming language before requesting predictions.", topics=[])
    try:
        try:
            language = ProgrammingLanguage(selected_language)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User language is not supported") from error
        topics = skill_prediction.predict_user_topics(user_id=current_user["user_id"], language=language)
    except skill_prediction.ModelNotTrainedError as error:
        return SkillProfileResponse(status="model_not_trained", message=str(error), language=language, topics=[])
    except skill_prediction.InsufficientSkillDataError as error:
        return SkillProfileResponse(status="insufficient_data", message=str(error), language=language, topics=[])
    except skill_prediction.SkillPredictionError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except (PyMongoError, RuntimeError) as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ML data is unavailable") from error
    return SkillProfileResponse(status="ready", language=language, topics=[TopicSkillPrediction.model_validate(topic) for topic in topics])


@router.post("/predict-skill", response_model=SkillPredictionResponse)
def predict_skill(
    request: SkillPredictionRequest,
    _authenticated_user: dict = Depends(get_current_user),
    model_service: SkillModelService = Depends(get_skill_model_service),
) -> SkillPredictionResponse:
    try:
        features = build_feature_row_from_rates(
            language=request.language.value,
            topic=request.topic.display_name,
            assessment_accuracy=request.assessment_accuracy,
            easy_success_rate=request.easy_success_rate,
            medium_success_rate=request.medium_success_rate,
            hard_success_rate=request.hard_success_rate,
            overall_success_rate=request.overall_success_rate,
            failure_rate=request.failure_rate,
            recent_success_rate=request.recent_success_rate,
            lesson_completion_rate=request.lesson_completion_rate,
            attempt_count=request.attempt_count,
        )
        prediction = model_service.predict_features(features)
    except SkillModelUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skill prediction model is unavailable",
        ) from error
    except SkillPredictionFailure as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Skill prediction failed",
        ) from error

    model_version = model_service.model_version
    feature_version = model_service.feature_version
    if model_version is None or feature_version is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skill prediction model metadata is unavailable",
        )
    log_prediction(
        features=features,
        prediction=prediction,
        model_version=model_version,
        feature_version=feature_version,
    )
    return SkillPredictionResponse(
        prediction=prediction,
        model_version=model_version,
        feature_version=feature_version,
        model_status="ready",
    )


@router.get("/monitoring")
def skill_model_monitoring(
    _authenticated_user: dict = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict:
    return monitoring_service.get_report()


@router.get("/monitoring/baseline")
def skill_model_monitoring_baseline(
    _authenticated_user: dict = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict:
    try:
        return monitoring_service.get_baseline()
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Monitoring baseline is unavailable",
        ) from error


@router.get("/health", response_model=SkillModelHealthResponse)
def skill_model_health(
    model_service: SkillModelService = Depends(get_skill_model_service),
) -> SkillModelHealthResponse | JSONResponse:
    if not model_service.ready:
        body = SkillModelHealthResponse(
            status="unavailable",
            model_status="unavailable",
            model_version=model_service.model_version,
            feature_version=model_service.feature_version,
        )
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body.model_dump())

    return SkillModelHealthResponse(
        status="healthy",
        model_status="ready",
        model_version=model_service.model_version,
        feature_version=model_service.feature_version,
    )
