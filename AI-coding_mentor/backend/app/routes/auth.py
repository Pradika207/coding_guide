from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import PyMongoError

from app.database.mongodb import get_database
from app.models.user import UserDocument
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    PublicUser,
    RegisterRequest,
)
from app.schemas.language import CurrentLanguageResponse, SelectLanguageRequest
from app.services.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _get_users_collection():
    try:
        return get_database().users
    except (PyMongoError, RuntimeError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register_user(request: RegisterRequest) -> AuthResponse:
    users = _get_users_collection()
    email = str(request.email).lower()

    if users.find_one({"email": email}, {"_id": 1}) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = UserDocument.new(
        user_id=str(uuid4()),
        name=request.name,
        email=email,
        password_hash=hash_password(request.password),
    )

    try:
        users.insert_one(user)
    except PyMongoError as error:
        if "duplicate" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            ) from error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error

    return AuthResponse(
        message="User registered successfully",
        user=UserDocument.to_public(user),
    )


@router.post("/login", response_model=AuthResponse)
def login_user(request: LoginRequest) -> AuthResponse:
    users = _get_users_collection()
    try:
        user = users.find_one({"email": str(request.email).lower()})
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error

    if user is None or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        access_token = create_access_token(user["user_id"])
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from error

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserDocument.to_public(user),
    )


@router.get("/me", response_model=PublicUser)
def read_current_user(current_user: dict = Depends(get_current_user)) -> PublicUser:
    return PublicUser.model_validate(UserDocument.to_public(current_user))


@router.put("/language", response_model=AuthResponse)
def select_language(
    request: SelectLanguageRequest,
    current_user: dict = Depends(get_current_user),
) -> AuthResponse:
    users = _get_users_collection()
    try:
        users.update_one(
            {"user_id": current_user["user_id"]},
            {"$set": {"selected_language": request.language.value}},
        )
        updated_user = users.find_one({"user_id": current_user["user_id"]})
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error

    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return AuthResponse(
        message="Programming language updated successfully",
        user=UserDocument.to_public(updated_user),
    )


@router.get("/language", response_model=CurrentLanguageResponse)
def read_current_language(
    current_user: dict = Depends(get_current_user),
) -> CurrentLanguageResponse:
    return CurrentLanguageResponse(selected_language=current_user.get("selected_language"))
