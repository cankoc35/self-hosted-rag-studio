"""
Generation orchestration.

Flow:
1) Retrieve relevant chunks (hybrid search)
2) Build prompt with context + source ids
3) Load recent conversation history
4) Ask Ollama LLM for final answer
5) Save messages to DB
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import HTTPException

from core import ollama
from models import repository as model_repository
from retrieval import service as retrieval_service

from . import prompts, repository


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").strip() or "http://ollama:11434"


def generation_model_env_default() -> str:
    return os.environ.get("GENERATION_MODEL", "qwen2.5:3b-instruct").strip() or "qwen2.5:3b-instruct"


def router_model_env_default() -> str:
    return os.environ.get("GENERATION_ROUTER_MODEL", "").strip() or generation_model_env_default()


async def selected_models() -> tuple[str, str]:
    row = await model_repository.get_model_settings()
    if row is None:
        return generation_model_env_default(), router_model_env_default()

    generation_model = str(row.get("generation_model") or "").strip() or generation_model_env_default()
    router_model = str(row.get("router_model") or "").strip() or router_model_env_default()
    return generation_model, router_model


def generation_timeout_s() -> float:
    return _env_float("GENERATION_TIMEOUT_S", 120.0)


def generation_temperature() -> float:
    return _env_float("GENERATION_TEMPERATURE", 0.2)


def generation_top_k_default() -> int:
    return _env_int("GENERATION_TOP_K", 5)


def generation_context_chars_per_chunk() -> int:
    return _env_int("GENERATION_CONTEXT_CHARS_PER_CHUNK", 2200)


def history_messages_limit() -> int:
    return _env_int("GENERATION_HISTORY_MESSAGES", 8)


def generation_max_output_tokens() -> int:
    return _env_int("GENERATION_MAX_OUTPUT_TOKENS", 200)


def route_timeout_s() -> float:
    return _env_float("GENERATION_ROUTE_TIMEOUT_S", 20.0)


def route_max_output_tokens() -> int:
    return _env_int("GENERATION_ROUTE_MAX_OUTPUT_TOKENS", 60)


def _parse_route(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return "rag"

    # Try strict JSON first.
    try:
        data = json.loads(raw)
        route = str((data or {}).get("route") or "").strip().lower()
        if route in {"casual", "rag"}:
            return route
    except Exception:
        pass

    # Try simple fallback (e.g. model returned plain text).
    lower = raw.lower()
    if "casual" in lower:
        return "casual"
    return "rag"


def _build_history_messages(
    history_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for row in history_rows:
        role = str(row.get("role") or "")
        if role not in {"user", "assistant"}:
            continue
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        messages.append({"role": role, "content": content})
    return messages


def _history_text_for_routing(history_rows: list[dict[str, Any]], *, max_items: int = 6, max_chars: int = 1200) -> str:
    """
    Compact text view of recent history for route classification.
    """
    if not history_rows:
        return "(empty)"

    selected = history_rows[-max_items:]
    lines: list[str] = []
    for row in selected:
        role = str(row.get("role") or "").strip()
        content = str(row.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        lines.append(f"{role}: {content}")

    text = "\n".join(lines).strip() or "(empty)"
    if len(text) > max_chars:
        return text[-max_chars:]
    return text


async def _classify_route_with_history(
    question: str,
    history_rows: list[dict[str, Any]],
    *,
    route_model_name: str,
) -> str:
    history_text = _history_text_for_routing(history_rows)
    try:
        text = await ollama.chat_messages(
            base_url=ollama_base_url(),
            model=route_model_name,
            messages=[
                {"role": "system", "content": prompts.route_system_prompt()},
                {"role": "user", "content": prompts.route_user_prompt(question, recent_history=history_text)},
            ],
            timeout_s=route_timeout_s(),
            temperature=0.0,
            max_output_tokens=route_max_output_tokens(),
        )
    except Exception:
        return "rag"
    return _parse_route(text)


# Build context from retrieved chunks (document knowledge), not chat history.
def _build_context(results: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    blocks: list[str] = []
    sources: list[dict[str, Any]] = []

    for i, row in enumerate(results, start=1):
        source_id = f"S{i}"
        text = str(row.get("text") or "").strip()
        filename = str(row.get("filename") or "unknown")
        chunk_index = int(row.get("chunk_index") or 0)

        blocks.append(
            f"[{source_id}] filename={filename} chunk_index={chunk_index}\n"
            f"{text}"
        )

        sources.append(
            {
                "source_id": source_id,
                "id": row.get("id"),
                "document_id": row.get("document_id"),
                "filename": filename,
                "chunk_index": chunk_index,
                "hybrid_score": row.get("hybrid_score"),
                "fts_score": row.get("fts_score"),
                "vec_sim": row.get("vec_sim"),
            }
        )

    return "\n\n".join(blocks), sources


async def chat(
    question: str,
    *,
    user_id: int,
    top_k: int | None = None,
    full_text_candidate_limit: int = 50,
    vector_candidate_limit: int = 50,
    full_text_weight: float = 0.5,
    vector_weight: float = 0.5,
    rrf_rank_constant: int = 60,
    debug: bool = False,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    question = (question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is empty.")

    try:
        conversation = await repository.get_or_create_conversation(conversation_id, user_id=user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found.") from exc
    conversation_key = str(conversation["conversation_key"])
    internal_conversation_id = int(conversation["id"])

    recent_messages = await repository.list_recent_messages(
        internal_conversation_id,
        limit=max(0, min(history_messages_limit(), 50)),
    )
    selected_generation_model, selected_route_model = await selected_models()
    route = await _classify_route_with_history(
        question,
        recent_messages,
        route_model_name=selected_route_model,
    )
    history_messages = _build_history_messages(recent_messages)

    if route == "casual":
        ollama_messages: list[dict[str, str]] = [{"role": "system", "content": prompts.casual_system_prompt()}]
        ollama_messages.extend(history_messages)
        ollama_messages.append({"role": "user", "content": question})

        await repository.insert_message(
            internal_conversation_id,
            role="user",
            content=question,
            metadata={"route": route},
        )
        answer = await ollama.chat_messages(
            base_url=ollama_base_url(),
            model=selected_generation_model,
            messages=ollama_messages,
            timeout_s=generation_timeout_s(),
            temperature=generation_temperature(),
            max_output_tokens=generation_max_output_tokens(),
        )
        await repository.insert_message(
            internal_conversation_id,
            role="assistant",
            content=answer,
            metadata={"route": route},
        )

        result: dict[str, Any] = {
            "conversation_id": conversation_key,
            "question": question,
            "answer": answer,
            "sources": [],
        }
        if debug:
            result["route"] = route
        return result

    limit = top_k if top_k is not None else generation_top_k_default()
    limit = max(1, min(limit, 20))
    retrieval_results = await retrieval_service.search_hybrid(
        question,
        user_id=user_id,
        limit=limit,
        text_chars=generation_context_chars_per_chunk(),
        full_text_candidate_limit=full_text_candidate_limit,
        vector_candidate_limit=vector_candidate_limit,
        full_text_weight=full_text_weight,
        vector_weight=vector_weight,
        rrf_rank_constant=rrf_rank_constant,
    )

    if not retrieval_results:
        fallback_answer = "I could not find relevant context for this question."
        await repository.insert_message(
            internal_conversation_id,
            role="user",
            content=question,
            metadata={"route": route},
        )
        await repository.insert_message(
            internal_conversation_id,
            role="assistant",
            content=fallback_answer,
            metadata={"route": route},
        )
        return {
            "conversation_id": conversation_key,
            "question": question,
            "answer": fallback_answer,
            "sources": [],
        }

    context_block, sources = _build_context(retrieval_results)
    ollama_messages: list[dict[str, str]] = [{"role": "system", "content": prompts.system_prompt()}]
    ollama_messages.extend(history_messages)
    ollama_messages.append({"role": "user", "content": prompts.user_prompt(question, context_block)})

    await repository.insert_message(
        internal_conversation_id,
        role="user",
        content=question,
        metadata={"route": route},
    )
    answer = await ollama.chat_messages(
        base_url=ollama_base_url(),
        model=selected_generation_model,
        messages=ollama_messages,
        timeout_s=generation_timeout_s(),
        temperature=generation_temperature(),
        max_output_tokens=generation_max_output_tokens(),
    )
    await repository.insert_message(
        internal_conversation_id,
        role="assistant",
        content=answer,
        sources=sources,
        metadata={"route": route},
    )

    result: dict[str, Any] = {
        "conversation_id": conversation_key,
        "question": question,
        "answer": answer,
        "sources": sources,
    }
    if debug:
        result["route"] = route
        result["retrieval"] = retrieval_results
    return result


async def get_conversation_messages(conversation_id: str, *, user_id: int, limit: int = 50) -> dict[str, Any]:
    conversation_id = (conversation_id or "").strip()
    if not conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id is empty.")

    conversation = await repository.get_conversation_by_key(conversation_id, user_id=user_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    rows = await repository.list_messages_by_key(
        conversation_id,
        user_id=user_id,
        limit=max(1, min(limit, 200)),
    )
    return {"conversation_id": conversation_id, "messages": rows}


async def list_conversations(
    *,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    search_query: str = "",
    similarity_threshold: float = 0.2,
) -> dict[str, Any]:
    rows = await repository.list_conversations(
        user_id=user_id,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
        search_query=search_query,
        similarity_threshold=max(0.0, min(similarity_threshold, 1.0)),
    )
    return {
        "conversations": rows,
        "limit": limit,
        "offset": offset,
        "search_query": search_query,
        "similarity_threshold": similarity_threshold,
        "count": len(rows),
    }
