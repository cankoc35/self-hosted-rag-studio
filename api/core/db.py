"""
Async database access helpers (raw SQL) using asyncpg.

This module owns the connection pool. FastAPI initializes it on startup and
closes it on shutdown (see `api/main.py`).

SQL parameter style:
- asyncpg uses positional placeholders: $1, $2, $3, ...
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg

_pool: asyncpg.Pool | None = None


def _sanitize_database_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url

    params = [(k, v) for (k, v) in parse_qsl(parts.query, keep_blank_values=True) if k != "sslmode"]
    query = urlencode(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set.")
    return _sanitize_database_url(url)


async def init_pool() -> None:
    global _pool
    if _pool is not None:
        return None
    _pool = await asyncpg.create_pool(
        dsn=database_url(),
        min_size=1,
        max_size=5,
        command_timeout=30,
    )


async def close_pool() -> None:
    global _pool
    if _pool is None:
        return None
    await _pool.close()
    _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool is not initialized. Call init_pool() on startup.")
    return _pool


def _record_to_dict(record: asyncpg.Record) -> dict[str, Any]:
    return dict(record)


async def fetch_one(sql: str, *args: Any) -> dict[str, Any] | None:
    """
    Run a query and return a single row as a dict (or None).
    """
    # takes sql query and the positional arguments
    row = await pool().fetchrow(sql, *args)
    return _record_to_dict(row) if row is not None else None


async def fetch_all(sql: str, *args: Any) -> list[dict[str, Any]]:
    """
    Run a query and return all rows as a list of dicts.
    """
    rows = await pool().fetch(sql, *args)
    return [_record_to_dict(r) for r in rows]


async def execute(sql: str, *args: Any) -> None:
    """
    Run a statement (INSERT/UPDATE/DELETE/DDL). No result returned.
    """
    await pool().execute(sql, *args)

