"""
Auth API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from . import dependencies, schemas, service

router = APIRouter(prefix="/auth")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


@router.post("/register", response_model=schemas.AuthResponse)
async def register(payload: schemas.RegisterRequest, request: Request) -> schemas.AuthResponse:
    return await service.register(
        payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )


@router.post("/login", response_model=schemas.AuthResponse)
async def login(payload: schemas.LoginRequest, request: Request) -> schemas.AuthResponse:
    return await service.login(
        payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )


@router.post("/refresh", response_model=schemas.TokenPairResponse)
async def refresh(payload: schemas.RefreshRequest, request: Request) -> schemas.TokenPairResponse:
    return await service.refresh_tokens(
        payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )


@router.post("/logout")
async def logout(payload: schemas.LogoutRequest) -> dict[str, bool]:
    # Current behavior: revoke the provided refresh token.
    # (Revoke-all flow can be added with authenticated current_user later.)
    return await service.logout(payload)


@router.get("/me", response_model=schemas.UserResponse)
async def me(access_token: str = Depends(dependencies.get_bearer_token)) -> schemas.UserResponse:
    return await service.me(access_token)
