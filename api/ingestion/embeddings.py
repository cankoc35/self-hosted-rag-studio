"""
Embedding pipeline (manual trigger).

Embeddings are generated via Ollama and stored in `chunks.embedding`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from fastapi import HTTPException

from core import ollama

from . import repository


DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_BATCH_SIZE = 16

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def embedding_model() -> str:
    return os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip() or DEFAULT_EMBEDDING_MODEL


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").strip() or "http://ollama:11434"


def expected_dim() -> int:
    """
    DB column is vector(768).
    """
    return 768


@dataclass(frozen=True)
class EmbedStats:
    document_id: int
    model: str
    embedded: int
    remaining: int


async def embed_document(document_id: int, *, user_id: int, batch_size: int | None = None) -> EmbedStats:
    """
    Generate embeddings for all chunks of a document that are missing embeddings.
    """
    model = embedding_model()
    base_url = ollama_base_url()
    bs = batch_size or _env_int("EMBEDDING_BATCH_SIZE", DEFAULT_BATCH_SIZE)
    if bs <= 0:
        bs = DEFAULT_BATCH_SIZE

    embedded = 0

    if not await repository.document_belongs_to_user(document_id, user_id=user_id):
        raise HTTPException(status_code=404, detail="Document not found.")

    # Loop until there is nothing left to embed for this document.
    while True:
        batch = await repository.fetch_chunks_needing_embedding(document_id, user_id=user_id, limit=bs)
        if not batch:
            break

        updates: list[tuple[int, list[float]]] = []
        for row in batch:
            vec = await ollama.embed_text(
                base_url=base_url,
                model=model,
                prompt=row["text"],
            )
            if len(vec) != expected_dim():
                raise HTTPException(
                    status_code=500,
                    detail=f"Embedding dim mismatch: expected {expected_dim()}, got {len(vec)}",
                )
            updates.append((int(row["id"]), vec))

        await repository.update_chunk_embeddings(updates, model=model)
        embedded += len(updates)

    remaining = await repository.count_chunks_needing_embedding(document_id, user_id=user_id)
    return EmbedStats(document_id=document_id, model=model, embedded=embedded, remaining=remaining)


async def embed_document_background(document_id: int, *, user_id: int) -> None:
    """
    BackgroundTasks entrypoint.

    This should never raise to the request path; we just log failures.
    The work is resumable because we only embed rows where `embedding IS NULL`.
    """
    try:
        stats = await embed_document(document_id, user_id=user_id)
        logger.info(
            "embedding_complete document_id=%s model=%s embedded=%s remaining=%s",
            stats.document_id,
            stats.model,
            stats.embedded,
            stats.remaining,
        )
    except Exception:
        logger.exception("embedding_failed document_id=%s user_id=%s", document_id, user_id)
