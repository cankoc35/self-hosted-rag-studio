"""
Auth dependencies for protected FastAPI routes.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from . import service


def _extract_bearer_token(authorization: str | None) -> str:
    raw = (authorization or "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )

    parts = raw.split(" ", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format.",
        )

    scheme, token = parts[0].strip().lower(), parts[1].strip()
    if scheme != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization must be: Bearer <token>.",
        )
    return token


async def get_bearer_token(authorization: str | None = Header(default=None)) -> str:
    return _extract_bearer_token(authorization)


async def get_current_user(access_token: str = Depends(get_bearer_token)) -> dict:
    return await service.get_user_from_access_token(access_token)
