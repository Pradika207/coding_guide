from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PublicUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    name: str
    email: EmailStr
    selected_language: str | None = None
    role: str = "student"
    created_at: datetime


class AuthResponse(BaseModel):
    message: str | None = None
    access_token: str | None = None
    token_type: str | None = None
    user: PublicUser
