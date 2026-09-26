from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from pymongo.errors import PyMongoError

from app.database.config import settings
from app.database.mongodb import get_database

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: str) -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expiration_minutes
    )
    payload = {"sub": user_id, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise credentials_exception
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as error:
        raise credentials_exception from error

    try:
        user = get_database().users.find_one({"user_id": user_id})
    except (PyMongoError, RuntimeError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error

    if user is None:
        raise credentials_exception
    return user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    role = str(current_user.get("role", "student")).lower()
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
