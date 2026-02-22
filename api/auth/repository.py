"""
Auth persistence helpers.
"""

from __future__ import annotations

from datetime import datetime, timezone

try:
    from core import db
except ModuleNotFoundError: 
    from api.core import db


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


async def create_user(*, email: str, password_hash: str, is_active: bool = True) -> dict:
    row = await db.fetch_one(
        """
        INSERT INTO users (email, password_hash, is_active)
        VALUES ($1, $2, $3)
        RETURNING id, email, is_active, created_at, updated_at
        """,
        normalize_email(email),
        password_hash,
        is_active,
    )
    if row is None:
        raise RuntimeError("Failed to create user.")
    return row


async def get_user_by_email(email: str) -> dict | None:
    return await db.fetch_one(
        """
        SELECT id, email, password_hash, is_active, created_at, updated_at
        FROM users
        WHERE lower(email) = lower($1)
        """,
        normalize_email(email),
    )


async def get_user_by_id(user_id: int) -> dict | None:
    return await db.fetch_one(
        """
        SELECT id, email, password_hash, is_active, created_at, updated_at
        FROM users
        WHERE id = $1
        """,
        user_id,
    )


async def insert_refresh_token(
    *,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    row = await db.fetch_one(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at, user_agent, ip_address)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, user_id, token_hash, expires_at, revoked_at,
                  replaced_by_token_id, created_at, last_used_at, user_agent, ip_address
        """,
        user_id,
        token_hash,
        expires_at,
        user_agent,
        ip_address,
    )
    if row is None:
        raise RuntimeError("Failed to insert refresh token.")
    return row


async def get_refresh_token_by_hash(token_hash: str) -> dict | None:
    return await db.fetch_one(
        """
        SELECT id, user_id, token_hash, expires_at, revoked_at,
               replaced_by_token_id, created_at, last_used_at, user_agent, ip_address
        FROM refresh_tokens
        WHERE token_hash = $1
        """,
        token_hash,
    )


async def mark_refresh_token_used(token_id: int) -> None:
    await db.execute(
        """
        UPDATE refresh_tokens
        SET last_used_at = now()
        WHERE id = $1
        """,
        token_id,
    )


async def revoke_refresh_token_by_hash(token_hash: str) -> bool:
    row = await db.fetch_one(
        """
        UPDATE refresh_tokens
        SET revoked_at = now()
        WHERE token_hash = $1
          AND revoked_at IS NULL
        RETURNING id
        """,
        token_hash,
    )
    return row is not None


async def revoke_refresh_token_by_id(token_id: int) -> bool:
    row = await db.fetch_one(
        """
        UPDATE refresh_tokens
        SET revoked_at = now()
        WHERE id = $1
          AND revoked_at IS NULL
        RETURNING id
        """,
        token_id,
    )
    return row is not None


async def revoke_all_refresh_tokens_for_user(user_id: int) -> None:
    await db.execute(
        """
        UPDATE refresh_tokens
        SET revoked_at = now()
        WHERE user_id = $1
          AND revoked_at IS NULL
        """,
        user_id,
    )


async def set_refresh_token_replacement(*, old_token_id: int, new_token_id: int) -> None:
    await db.execute(
        """
        UPDATE refresh_tokens
        SET replaced_by_token_id = $2
        WHERE id = $1
        """,
        old_token_id,
        new_token_id,
    )
