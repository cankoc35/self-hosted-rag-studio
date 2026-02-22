"""
Auth security helpers.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from typing import Any

import bcrypt
import jwt


class AuthSecurityError(RuntimeError):
    pass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def jwt_secret() -> str:
    # Local default keeps development simple.
    # In production, set JWT_SECRET in environment.
    return os.environ.get("JWT_SECRET", "dev-change-this-secret").strip() or "dev-change-this-secret"


def jwt_algorithm() -> str:
    return os.environ.get("JWT_ALG", "HS256").strip() or "HS256"


def access_token_expire_minutes() -> int:
    return _env_int("ACCESS_TOKEN_EXPIRE_MIN", 15)


def refresh_token_expire_days() -> int:
    return _env_int("REFRESH_TOKEN_EXPIRE_DAYS", 30)


def now_epoch_s() -> int:
    return int(time.time())


def hash_password(plain_password: str) -> str:
    password = (plain_password or "").encode("utf-8")
    if not password:
        raise AuthSecurityError("Password is empty.")
    return bcrypt.hashpw(password, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    password = (plain_password or "").encode("utf-8")
    hashed = (password_hash or "").encode("utf-8")
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(password, hashed)
    except ValueError:
        return False


def build_access_token(*, user_id: int, email: str) -> str:
    issued_at = now_epoch_s()
    expires_at = issued_at + (access_token_expire_minutes() * 60)

    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "iat": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(payload, jwt_secret(), algorithm=jwt_algorithm())


def decode_access_token(token: str) -> dict[str, Any]:
    raw = (token or "").strip()
    if not raw:
        raise AuthSecurityError("Access token is empty.")

    try:
        payload = jwt.decode(raw, jwt_secret(), algorithms=[jwt_algorithm()])
    except jwt.InvalidTokenError as exc:
        raise AuthSecurityError("Invalid access token.") from exc

    token_type = str(payload.get("type") or "").strip().lower()
    if token_type != "access":
        raise AuthSecurityError("Token is not an access token.")

    return payload


def build_refresh_token() -> str:
    # URL-safe random string for client storage/transmission.
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_refresh_token: str) -> str:
    token = (raw_refresh_token or "").encode("utf-8")
    if not token:
        raise AuthSecurityError("Refresh token is empty.")
    return hashlib.sha256(token).hexdigest()
