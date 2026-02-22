"""
Auth business logic.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from . import repository, schemas, security


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_user_response(user_row: dict) -> schemas.UserResponse:
    return schemas.UserResponse(
        id=int(user_row["id"]),
        email=str(user_row["email"]),
        is_active=bool(user_row["is_active"]),
        created_at=user_row["created_at"],
    )


async def _issue_token_pair(
    *,
    user_row: dict,
    user_agent: str | None = None,
    ip_address: str | None = None,
    replaced_token_id: int | None = None,
) -> schemas.TokenPairResponse:
    user_id = int(user_row["id"])
    email = str(user_row["email"])

    access_token = security.build_access_token(user_id=user_id, email=email)
    raw_refresh_token = security.build_refresh_token()
    refresh_hash = security.hash_refresh_token(raw_refresh_token)
    expires_at = _utc_now() + timedelta(days=security.refresh_token_expire_days())

    refresh_row = await repository.insert_refresh_token(
        user_id=user_id,
        token_hash=refresh_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    if replaced_token_id is not None:
        await repository.set_refresh_token_replacement(
            old_token_id=replaced_token_id,
            new_token_id=int(refresh_row["id"]),
        )

    return schemas.TokenPairResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
    )


async def register(
    payload: schemas.RegisterRequest,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> schemas.AuthResponse:
    existing = await repository.get_user_by_email(payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )

    password_hash = security.hash_password(payload.password)
    user_row = await repository.create_user(email=payload.email, password_hash=password_hash)

    tokens = await _issue_token_pair(
        user_row=user_row,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    user = _to_user_response(user_row)
    return schemas.AuthResponse(user=user, tokens=tokens)


async def login(
    payload: schemas.LoginRequest,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> schemas.AuthResponse:
    user_row = await repository.get_user_by_email(payload.email)
    if user_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not bool(user_row.get("is_active", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive.",
        )

    is_valid = security.verify_password(payload.password, str(user_row.get("password_hash") or ""))
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    tokens = await _issue_token_pair(
        user_row=user_row,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    user = _to_user_response(user_row)
    return schemas.AuthResponse(user=user, tokens=tokens)


async def refresh_tokens(
    payload: schemas.RefreshRequest,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> schemas.TokenPairResponse:
    incoming_refresh = (payload.refresh_token or "").strip()
    if not incoming_refresh:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token is required.",
        )

    incoming_hash = security.hash_refresh_token(incoming_refresh)
    old_token_row = await repository.get_refresh_token_by_hash(incoming_hash)
    if old_token_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    if old_token_row.get("revoked_at") is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is revoked.",
        )

    expires_at = old_token_row.get("expires_at")
    if not isinstance(expires_at, datetime) or expires_at <= _utc_now():
        # Revoke expired token as cleanup.
        await repository.revoke_refresh_token_by_id(int(old_token_row["id"]))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is expired.",
        )

    user_row = await repository.get_user_by_id(int(old_token_row["user_id"]))
    if user_row is None or not bool(user_row.get("is_active", False)):
        await repository.revoke_refresh_token_by_id(int(old_token_row["id"]))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token owner.",
        )

    await repository.mark_refresh_token_used(int(old_token_row["id"]))
    await repository.revoke_refresh_token_by_id(int(old_token_row["id"]))

    return await _issue_token_pair(
        user_row=user_row,
        user_agent=user_agent,
        ip_address=ip_address,
        replaced_token_id=int(old_token_row["id"]),
    )


async def logout(
    payload: schemas.LogoutRequest,
    *,
    current_user_id: int | None = None,
) -> dict[str, bool]:
    # If specific refresh token is provided, revoke only that token.
    refresh_token = (payload.refresh_token or "").strip()
    if refresh_token:
        token_hash = security.hash_refresh_token(refresh_token)
        await repository.revoke_refresh_token_by_hash(token_hash)
        return {"ok": True}

    # If token is not provided, but user is authenticated, revoke all sessions.
    if current_user_id is not None:
        await repository.revoke_all_refresh_tokens_for_user(current_user_id)
        return {"ok": True}

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Provide refresh_token or authenticated user.",
    )


async def get_user_from_access_token(access_token: str) -> dict:
    try:
        payload = security.decode_access_token(access_token)
    except security.AuthSecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    subject = str(payload.get("sub") or "").strip()
    if not subject.isdigit():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token subject.",
        )

    user_row = await repository.get_user_by_id(int(subject))
    if user_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    if not bool(user_row.get("is_active", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive.",
        )
    return user_row


async def me(access_token: str) -> schemas.UserResponse:
    user_row = await get_user_from_access_token(access_token)
    return _to_user_response(user_row)
