"""
Generation persistence helpers (chat history).
"""

from __future__ import annotations

import json
from uuid import uuid4

from core import db


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=True)


async def get_conversation_by_key(conversation_key: str, *, user_id: int) -> dict | None:
    return await db.fetch_one(
        """
        SELECT id, conversation_key, user_id, metadata, created_at, updated_at
        FROM conversations
        WHERE conversation_key = $1
          AND user_id = $2
        """,
        conversation_key,
        user_id,
    )


async def get_or_create_conversation(conversation_key: str | None, *, user_id: int) -> dict:
    key = (conversation_key or "").strip() or str(uuid4())
    row = await db.fetch_one(
        """
        INSERT INTO conversations (conversation_key, user_id)
        VALUES ($1, $2)
        ON CONFLICT (conversation_key) DO UPDATE
        SET updated_at = conversations.updated_at
        WHERE conversations.user_id = EXCLUDED.user_id
        RETURNING id, conversation_key, user_id, metadata, created_at, updated_at
        """,
        key,
        user_id,
    )
    if row is None:
        raise RuntimeError("Conversation not found for this user.")
    return row


async def insert_message(
    conversation_id: int,
    *,
    role: str,
    content: str,
    sources: list[dict] | None = None,
    metadata: dict | None = None,
) -> dict:
    row = await db.fetch_one(
        """
        INSERT INTO messages (conversation_id, role, content, sources, metadata)
        VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
        RETURNING id, conversation_id, role, content, sources, metadata, created_at
        """,
        conversation_id,
        role,
        content,
        _json_dumps(sources or []),
        _json_dumps(metadata or {}),
    )
    await db.execute("UPDATE conversations SET updated_at = now() WHERE id = $1", conversation_id)
    if row is None:
        raise RuntimeError("Failed to insert message.")
    return row


async def list_recent_messages(conversation_id: int, *, limit: int = 8) -> list[dict]:
    rows = await db.fetch_all(
        """
        SELECT id, conversation_id, role, content, sources, metadata, created_at
        FROM messages
        WHERE conversation_id = $1
        ORDER BY created_at DESC, id DESC
        LIMIT $2
        """,
        conversation_id,
        limit,
    )
    rows.reverse()
    return rows


async def list_messages_by_key(conversation_key: str, *, user_id: int, limit: int = 50) -> list[dict]:
    return await db.fetch_all(
        """
        SELECT x.id, x.conversation_id, x.role, x.content, x.sources, x.metadata, x.created_at
        FROM (
          SELECT m.id, m.conversation_id, m.role, m.content, m.sources, m.metadata, m.created_at
          FROM messages m
          JOIN conversations c ON c.id = m.conversation_id
          WHERE c.conversation_key = $1
            AND c.user_id = $2
          ORDER BY m.created_at DESC, m.id DESC
          LIMIT $3
        ) x
        ORDER BY x.created_at ASC, x.id ASC
        """,
        conversation_key,
        user_id,
        limit,
    )


async def list_conversations(
    *,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    search_query: str = "",
    similarity_threshold: float = 0.2,
) -> list[dict]:
    """
    List conversations for a user, newest first.
    Includes message count and a short preview from the latest message.
    If search_query is set, applies fuzzy matching over all message content.
    """
    q = (search_query or "").strip().lower()
    return await db.fetch_all(
        """
        WITH matched AS (
          SELECT
            m.conversation_id,
            max(similarity(lower(m.content), $4)) AS best_similarity
          FROM messages m
          JOIN conversations c2 ON c2.id = m.conversation_id
          WHERE c2.user_id = $1
            AND $4 <> ''
            AND (
              lower(m.content) % $4
              OR similarity(lower(m.content), $4) >= $5
              OR lower(m.content) LIKE ('%' || $4 || '%')
            )
          GROUP BY m.conversation_id
        )
        SELECT
          c.conversation_key AS conversation_id,
          c.created_at,
          c.updated_at,
          COALESCE(msg.message_count, 0)::int AS message_count,
          msg.last_message_preview,
          COALESCE(matched.best_similarity, 0.0)::float8 AS best_similarity
        FROM conversations c
        LEFT JOIN LATERAL (
          SELECT
            count(*)::int AS message_count,
            (
              SELECT left(m2.content, 180)
              FROM messages m2
              WHERE m2.conversation_id = c.id
              ORDER BY m2.created_at DESC, m2.id DESC
              LIMIT 1
            ) AS last_message_preview
          FROM messages m
          WHERE m.conversation_id = c.id
        ) msg ON true
        LEFT JOIN matched ON matched.conversation_id = c.id
        WHERE c.user_id = $1
          AND ($4 = '' OR matched.conversation_id IS NOT NULL)
        ORDER BY
          CASE WHEN $4 <> '' THEN COALESCE(matched.best_similarity, 0.0) END DESC,
          c.updated_at DESC,
          c.id DESC
        LIMIT $2
        OFFSET $3
        """,
        user_id,
        limit,
        offset,
        q,
        similarity_threshold,
    )
