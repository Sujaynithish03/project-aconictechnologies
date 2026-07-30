"""Auth request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import BCRYPT_MAX_BYTES


class UserCredentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(
                f"Password must be at most {BCRYPT_MAX_BYTES} bytes long."
            )
        if value.strip() != value:
            raise ValueError("Password must not start or end with whitespace.")
        if not any(char.isalpha() for char in value):
            raise ValueError("Password must contain at least one letter.")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one number.")
        return value


class LoginRequest(BaseModel):
    """Login is intentionally lenient — never leak policy details on sign-in."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
