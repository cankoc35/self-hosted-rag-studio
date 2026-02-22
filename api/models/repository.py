"""
Model catalog persistence (raw SQL).
"""

from __future__ import annotations

from core import db


async def list_available_models(
    *,
    search_query: str = "",
    similarity_threshold: float = 0.2,
) -> list[dict]:
    """
    Return enabled generation models from DB allowlist.
    """
    q = (search_query or "").strip().lower()
    return await db.fetch_all(
        """
        SELECT id, name, is_enabled, is_active, created_at, updated_at
        FROM llm_models
        WHERE is_enabled = true
          AND (
            $1 = ''
            OR lower(name) % $1
            OR similarity(lower(name), $1) >= $2
            OR lower(name) LIKE ('%' || $1 || '%')
          )
        ORDER BY
          CASE WHEN $1 <> '' THEN similarity(lower(name), $1) END DESC,
          name ASC
        """
        ,
        q,
        similarity_threshold,
    )


async def is_allowed_model(model_name: str) -> bool:
    row = await db.fetch_one(
        """
        SELECT 1 AS ok
        FROM llm_models
        WHERE name = $1
          AND is_enabled = true
        LIMIT 1
        """,
        model_name,
    )
    return row is not None


async def get_active_model() -> dict | None:
    return await db.fetch_one(
        """
        SELECT id, name, is_enabled, is_active, created_at, updated_at
        FROM llm_models
        WHERE is_active = true
          AND is_enabled = true
        LIMIT 1
        """
    )


async def get_active_model_name() -> str | None:
    row = await get_active_model()
    if row is None:
        return None
    return str(row["name"])


async def set_active_model(model_name: str) -> dict | None:
    return await db.fetch_one(
        """
        WITH cleared AS (
            UPDATE llm_models
            SET is_active = false
            WHERE is_active = true
            RETURNING id
        ),
        activated AS (
            UPDATE llm_models
            SET is_active = true,
                updated_at = now()
            WHERE name = $1
              AND is_enabled = true
            RETURNING id, name, is_enabled, is_active, created_at, updated_at
        )
        SELECT id, name, is_enabled, is_active, created_at, updated_at
        FROM activated
        LIMIT 1
        """,
        model_name,
    )


async def clear_active_model() -> None:
    await db.execute(
        """
        UPDATE llm_models
        SET is_active = false
        WHERE is_active = true
        """
    )


async def get_model_settings() -> dict | None:
    return await db.fetch_one(
        """
        SELECT generation_model, router_model, updated_at
        FROM model_settings
        WHERE id = 1
        LIMIT 1
        """
    )


async def upsert_model_settings(*, generation_model: str, router_model: str) -> dict:
    row = await db.fetch_one(
        """
        INSERT INTO model_settings (id, generation_model, router_model)
        VALUES (1, $1, $2)
        ON CONFLICT (id) DO UPDATE
        SET generation_model = EXCLUDED.generation_model,
            router_model = EXCLUDED.router_model,
            updated_at = now()
        RETURNING generation_model, router_model, updated_at
        """,
        generation_model,
        router_model,
    )
    if row is None:
        raise RuntimeError("Failed to upsert model settings.")
    return row
