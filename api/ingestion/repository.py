"""
Ingestion persistence.
This module is where ingestion-related SQL lives.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from core import db


def _json_arg(value: dict[str, Any] | None) -> str | None:
    """
    asyncpg does not automatically encode Python dicts for json/jsonb parameters.
    We pass JSON as a string and cast to jsonb in SQL.
    """
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True)


def _vector_literal(vec: list[float]) -> str:
    """
    Serialize a Python list of floats into a pgvector literal.

    We pass this as text and cast it to `vector(768)` in SQL: $2::vector.
    """
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


async def list_documents(*, user_id: int, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """
    List active (not soft-deleted) documents for a user.
    """
    rows = await db.fetch_all(
        """
        SELECT
          d.id,
          d.filename,
          d.content_type,
          d.size_bytes,
          d.created_at,
          COALESCE(stats.chunk_count, 0) AS chunk_count,
          COALESCE(stats.embedded_chunk_count, 0) AS embedded_chunk_count
        FROM documents d
        LEFT JOIN LATERAL (
          SELECT
            count(*) AS chunk_count,
            count(*) FILTER (WHERE c.embedding IS NOT NULL) AS embedded_chunk_count
          FROM chunks c
          WHERE c.document_id = d.id
        ) stats ON true
        WHERE d.user_id = $1
          AND d.deleted_at IS NULL
        ORDER BY d.created_at DESC, d.id DESC
        LIMIT $2
        OFFSET $3
        """,
        user_id,
        limit,
        offset,
    )
    return rows


async def soft_delete_document(document_id: int, *, user_id: int) -> dict[str, Any] | None:
    """
    Soft-delete a document owned by the given user.
    Returns deleted row metadata, or None when not found/already deleted.
    """
    return await db.fetch_one(
        """
        UPDATE documents
        SET deleted_at = now()
        WHERE id = $1
          AND user_id = $2
          AND deleted_at IS NULL
        RETURNING id, deleted_at
        """,
        document_id,
        user_id,
    )


async def document_belongs_to_user(document_id: int, *, user_id: int) -> bool:
    row = await db.fetch_one(
        """
        SELECT 1 AS ok
        FROM documents
        WHERE id = $1
          AND user_id = $2
          AND deleted_at IS NULL
        LIMIT 1
        """,
        document_id,
        user_id,
    )
    return row is not None


async def fetch_chunks_needing_embedding(
    document_id: int,
    *,
    user_id: int,
    limit: int,
) -> list[dict[str, Any]]:
    """
    Fetch chunk rows that still need embeddings.
    """
    rows = await db.fetch_all(
        """
        SELECT c.id, c.chunk_index, c.text
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.document_id = $1
          AND d.user_id = $2
          AND d.deleted_at IS NULL
          AND c.embedding IS NULL
        ORDER BY c.chunk_index
        LIMIT $3
        """,
        document_id,
        user_id,
        limit,
    )
    return rows


async def count_chunks_needing_embedding(document_id: int, *, user_id: int) -> int:
    row = await db.fetch_one(
        """
        SELECT count(*) AS n
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.document_id = $1
          AND d.user_id = $2
          AND d.deleted_at IS NULL
          AND c.embedding IS NULL
        """,
        document_id,
        user_id,
    )
    return int((row or {}).get("n", 0))


async def update_chunk_embeddings(
    updates: list[tuple[int, list[float]]],
    *,
    model: str,
) -> None:
    """
    Bulk update chunk embeddings.

    `updates` is [(chunk_id, embedding_vector), ...]
    """
    if not updates:
        return

    records = [(chunk_id, _vector_literal(vec), model) for (chunk_id, vec) in updates]

    pool = db.pool()
    async with pool.acquire() as conn:  # type: asyncpg.Connection
        async with conn.transaction():
            await conn.executemany(
                """
                UPDATE chunks
                SET embedding = $2::vector,
                    embedding_model = $3,
                    embedded_at = now()
                WHERE id = $1
                  AND embedding IS NULL
                """,
                records,
            )


async def insert_document_and_chunks(
    *,
    user_id: int,
    filename: str,
    content_type: str | None,
    size_bytes: int,
    extracted_text: str,
    chunks: list[str],
    metadata: dict[str, Any] | None = None,
) -> tuple[int, int]:
    """
    Insert a document + its chunks in a single transaction.

    Returns (document_id, chunk_count).
    """
    if not chunks:
        raise RuntimeError("insert_document_and_chunks called with empty chunks list.")

    pool = db.pool()
    async with pool.acquire() as conn:  # type: asyncpg.Connection
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO documents (user_id, filename, content_type, size_bytes, extracted_text, metadata)
                VALUES ($1, $2, $3, $4, $5, COALESCE($6::jsonb, '{}'::jsonb))
                RETURNING id
                """,
                user_id,
                filename,
                content_type,
                size_bytes,
                extracted_text,
                _json_arg(metadata),
            )
            if row is None or "id" not in row:
                raise RuntimeError("Failed to insert document.")

            document_id = int(row["id"])

            # Bulk insert chunks.
            records = [(document_id, i, text) for i, text in enumerate(chunks)]
            await conn.executemany(
                "INSERT INTO chunks (document_id, chunk_index, text) VALUES ($1, $2, $3)",
                records,
            )

            return document_id, len(records)


async def insert_document(
    *,
    user_id: int,
    filename: str,
    content_type: str | None,
    size_bytes: int,
    extracted_text: str,
    metadata: dict[str, Any] | None = None,
) -> int:
    """
    Insert a document and return its id.

    Schema comes from the dbmate migration:
    - documents(id bigserial, filename, content_type, size_bytes, extracted_text, metadata, created_at)
    """
    row = await db.fetch_one(
        """
        INSERT INTO documents (user_id, filename, content_type, size_bytes, extracted_text, metadata)
        VALUES ($1, $2, $3, $4, $5, COALESCE($6::jsonb, '{}'::jsonb))
        RETURNING id
        """,
        user_id,
        filename,
        content_type,
        size_bytes,
        extracted_text,
        _json_arg(metadata),
    )
    if row is None or "id" not in row:
        raise RuntimeError("Failed to insert document.")
    return int(row["id"])
