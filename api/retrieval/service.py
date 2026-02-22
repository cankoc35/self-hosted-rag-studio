"""
Retrieval service (orchestration).

This is where we:
- generate a query embedding via Ollama (for vector/hybrid search)
- call Postgres retrieval queries (repository)
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException

from core import ollama

from . import repository


EXPECTED_EMBED_DIM = 768


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def embedding_model() -> str:
    return os.environ.get("EMBEDDING_MODEL", "nomic-embed-text").strip() or "nomic-embed-text"


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").strip() or "http://ollama:11434"


async def _query_embedding(query: str) -> list[float]:
    vec = await ollama.embed_text(
        base_url=ollama_base_url(),
        model=embedding_model(),
        prompt=query,
    )
    if len(vec) != EXPECTED_EMBED_DIM:
        raise HTTPException(
            status_code=500,
            detail=f"Embedding dim mismatch: expected {EXPECTED_EMBED_DIM}, got {len(vec)}",
        )
    return vec


async def search_fts(query: str, *, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    return await repository.search_fts(query, user_id=user_id, limit=limit)


async def search_vector(query: str, *, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    vec = await _query_embedding(query)
    return await repository.search_vector(vec, user_id=user_id, embedding_model=embedding_model(), limit=limit)


async def search_hybrid(
    query: str,
    *,
    user_id: int,
    limit: int = 10,
    text_chars: int = repository.TEXT_PREVIEW_CHARS,
    full_text_candidate_limit: int = 50,
    vector_candidate_limit: int = 50,
    full_text_weight: float = 0.5,
    vector_weight: float = 0.5,
    rrf_rank_constant: int = 60,
) -> list[dict[str, Any]]:
    vec = await _query_embedding(query)
    return await repository.search_hybrid(
        query,
        vec,
        user_id=user_id,
        embedding_model=embedding_model(),
        limit=limit,
        text_chars=text_chars,
        full_text_candidate_limit=full_text_candidate_limit,
        vector_candidate_limit=vector_candidate_limit,
        full_text_weight=full_text_weight,
        vector_weight=vector_weight,
        rrf_rank_constant=rrf_rank_constant,
    )
