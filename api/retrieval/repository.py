"""
Retrieval SQL (raw).

This module contains Postgres queries for:
- full-text search (FTS) over `chunks.tsv`
- vector search over `chunks.embedding`
- hybrid ranking (FTS + vector) with rank fusion in SQL
"""

from __future__ import annotations

from typing import Any

from core import db


def _vector_literal(vec: list[float]) -> str:
    """
    Serialize a Python list of floats into a pgvector literal: "[1.0,2.0,...]".

    We pass this as text and cast it to `vector` in SQL ($n::vector).
    """
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"

TEXT_PREVIEW_CHARS = 120


async def search_fts(query_text: str, *, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    """
    Full-text search over chunks. Uses websearch syntax (quotes, -, OR, etc).
    """
    return await db.fetch_all(
        """
        WITH q AS (
          SELECT websearch_to_tsquery('english', $1) AS tsq
        )
        SELECT
          c.id,
          c.document_id,
          d.filename,
          c.chunk_index,
          regexp_replace(left(c.text, $3), E'\\s+', ' ', 'g') AS text,
          ts_rank_cd(c.tsv, (SELECT tsq FROM q)) AS fts_score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.tsv @@ (SELECT tsq FROM q)
          AND d.user_id = $2
          AND d.deleted_at IS NULL
        ORDER BY fts_score DESC
        LIMIT $4
        """,
        query_text,
        user_id,
        TEXT_PREVIEW_CHARS,
        limit,
    )


async def search_vector(
    query_vec: list[float],
    *,
    user_id: int,
    embedding_model: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Vector similarity search over chunk embeddings (cosine distance).
    """
    qvec = _vector_literal(query_vec)
    return await db.fetch_all(
        """
        SELECT
          c.id,
          c.document_id,
          d.filename,
          c.chunk_index,
          regexp_replace(left(c.text, $4), E'\\s+', ' ', 'g') AS text,
          (c.embedding <=> $1::vector) AS vec_dist,
          (1.0::float8 - (c.embedding <=> $1::vector)) AS vec_sim
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.embedding IS NOT NULL
          AND c.embedding_model = $2
          AND d.user_id = $3
          AND d.deleted_at IS NULL
        ORDER BY vec_dist ASC
        LIMIT $5
        """,
        qvec,
        embedding_model,
        user_id,
        TEXT_PREVIEW_CHARS,
        limit,
    )


async def search_hybrid(
    query_text: str,
    query_vec: list[float],
    *,
    user_id: int,
    embedding_model: str,
    limit: int = 10,
    text_chars: int = TEXT_PREVIEW_CHARS,
    full_text_candidate_limit: int = 50,
    vector_candidate_limit: int = 50,
    full_text_weight: float = 0.5,
    vector_weight: float = 0.5,
    rrf_rank_constant: int = 60,
) -> list[dict[str, Any]]:
    """
    Hybrid search with rank fusion done in Postgres.

    We create two candidate sets:
    - FTS top full_text_candidate_limit
    - vector top vector_candidate_limit

    Then fuse them with Reciprocal Rank Fusion (RRF):
      score = w_fts * 1/(rrf_rank_constant + fts_rank) + w_vec * 1/(rrf_rank_constant + vec_rank)
    """
    qvec = _vector_literal(query_vec)
    return await db.fetch_all(
        """
        WITH
        q AS (
          SELECT
            websearch_to_tsquery('simple', $1) AS tsq,
            $2::vector AS qvec
        ),
        fts AS (
          SELECT
            c.id,
            c.document_id,
            c.chunk_index,
            regexp_replace(left(c.text, $3), E'\\s+', ' ', 'g') AS text,
            ts_rank_cd(c.tsv, (SELECT tsq FROM q)) AS fts_score,
            row_number() OVER (ORDER BY ts_rank_cd(c.tsv, (SELECT tsq FROM q)) DESC) AS fts_rank
          FROM chunks c
          JOIN documents d ON d.id = c.document_id
          WHERE c.tsv @@ (SELECT tsq FROM q)
            AND d.user_id = $11
            AND d.deleted_at IS NULL
          ORDER BY fts_score DESC
          LIMIT $4
        ),
        vec AS (
          SELECT
            c.id,
            c.document_id,
            c.chunk_index,
            regexp_replace(left(c.text, $3), E'\\s+', ' ', 'g') AS text,
            (c.embedding <=> (SELECT qvec FROM q)) AS vec_dist,
            row_number() OVER (ORDER BY (c.embedding <=> (SELECT qvec FROM q)) ASC) AS vec_rank
          FROM chunks c
          JOIN documents d ON d.id = c.document_id
          WHERE c.embedding IS NOT NULL
            AND c.embedding_model = $5
            AND d.user_id = $11
            AND d.deleted_at IS NULL
          ORDER BY vec_dist ASC
          LIMIT $6
        ),
        merged AS (
          SELECT
            COALESCE(fts.id, vec.id) AS id,
            COALESCE(fts.document_id, vec.document_id) AS document_id,
            COALESCE(fts.chunk_index, vec.chunk_index) AS chunk_index,
            COALESCE(fts.text, vec.text) AS text,
            fts.fts_score,
            fts.fts_rank,
            vec.vec_dist,
            vec.vec_rank,
            COALESCE(1.0::float8 / ($7 + fts.fts_rank), 0.0::float8) AS rrf_fts,
            COALESCE(1.0::float8 / ($7 + vec.vec_rank), 0.0::float8) AS rrf_vec
          FROM fts
          FULL OUTER JOIN vec USING (id)
        )
        SELECT
          m.id,
          m.document_id,
          d.filename,
          m.chunk_index,
          m.text,
          m.fts_score::float8 AS fts_score,
          m.fts_rank::int AS fts_rank,
          m.vec_dist::float8 AS vec_dist,
          (1.0::float8 - m.vec_dist)::float8 AS vec_sim,
          m.vec_rank::int AS vec_rank,
          m.rrf_fts::float8 AS rrf_fts,
          m.rrf_vec::float8 AS rrf_vec,
          (($8::float8 * m.rrf_fts + $9::float8 * m.rrf_vec))::float8 AS hybrid_score,
          (m.fts_score IS NOT NULL) AS matched_fts,
          (m.vec_dist IS NOT NULL) AS matched_vec
        FROM merged m
        JOIN documents d ON d.id = m.document_id
        WHERE d.deleted_at IS NULL
        ORDER BY hybrid_score DESC
        LIMIT $10
        """,
        query_text,
        qvec,
        text_chars,
        full_text_candidate_limit,
        embedding_model,
        vector_candidate_limit,
        rrf_rank_constant,
        full_text_weight,
        vector_weight,
        limit,
        user_id,
    )
