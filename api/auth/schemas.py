"""
Auth API schemas (request/response models).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20)


class LogoutRequest(BaseModel):
    # If omitted, service can choose to revoke all user tokens.
    refresh_token: str | None = Field(default=None, min_length=20)


class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenPairResponse
