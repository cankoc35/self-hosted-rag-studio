"""
Model-management business logic.

Scope:
- generation model catalog (allowlist from DB)
- installed model detection from local Ollama
- pull/download model through Ollama
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import HTTPException

from . import repository


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").strip() or "http://ollama:11434"


def generation_model_env_default() -> str:
    return os.environ.get("GENERATION_MODEL", "qwen2.5:3b-instruct").strip() or "qwen2.5:3b-instruct"


def router_model_env_default() -> str:
    return os.environ.get("GENERATION_ROUTER_MODEL", "").strip() or generation_model_env_default()


async def available_models(
    *,
    search_query: str = "",
    similarity_threshold: float = 0.2,
) -> list[dict]:
    rows = await repository.list_available_models(
        search_query=search_query,
        similarity_threshold=max(0.0, min(similarity_threshold, 1.0)),
    )

    default_names = {generation_model_env_default(), router_model_env_default()}
    existing = {str(row["name"]).strip() for row in rows}
    q = (search_query or "").strip().lower()
    for default_name in default_names:
        if not default_name or default_name in existing:
            continue

        lower_name = default_name.lower()
        if q and (q not in lower_name):
            continue

        if default_name and default_name not in existing:
            rows.append(
                {
                    "id": 0,
                    "name": default_name,
                    "is_enabled": True,
                    "is_active": False,
                    "created_at": None,
                    "updated_at": None,
                }
            )
            existing.add(default_name)

    return [
        {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "is_enabled": bool(row["is_enabled"]),
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def _parse_tags_payload(data: dict[str, Any]) -> list[dict]:
    models = data.get("models")
    if not isinstance(models, list):
        return []

    parsed: list[dict] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        parsed.append(
            {
                "name": name,
                "size": item.get("size"),
                "digest": item.get("digest"),
                "modified_at": item.get("modified_at"),
            }
        )
    return parsed


async def installed_models() -> list[dict]:
    base_url = ollama_base_url()
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
            resp = await client.get("/api/tags")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to call Ollama tags endpoint: {exc}") from exc

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama tags request failed with status {resp.status_code}: {resp.text[:300]}",
        )

    data: dict[str, Any] = resp.json()
    return _parse_tags_payload(data)


async def _installed_name_set() -> set[str]:
    installed_set = {str(item.get("name") or "").strip() for item in await installed_models()}
    installed_set.discard("")
    return installed_set


def _is_allowed_or_default(model_name: str, *, is_allowed: bool) -> bool:
    defaults = {generation_model_env_default(), router_model_env_default()}
    return is_allowed or model_name in defaults


async def model_config() -> dict:
    row = await repository.get_model_settings()
    if row is None:
        generation_model = generation_model_env_default()
        router_model = router_model_env_default()
        source = "env"
    else:
        generation_model = str(row["generation_model"]).strip()
        router_model = str(row["router_model"]).strip()
        source = "db"

    installed_set = await _installed_name_set()
    return {
        "generation_model": generation_model,
        "router_model": router_model,
        "source": source,
        "generation_model_installed": generation_model in installed_set,
        "router_model_installed": router_model in installed_set,
    }


async def active_model() -> dict:
    config = await model_config()
    return {
        "model": config["generation_model"],
        "source": config["source"],
        "is_installed": config["generation_model_installed"],
    }


async def select_generation_model(model_name: str) -> dict:
    model_name = (model_name or "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="Model name is required.")

    is_allowed = await repository.is_allowed_model(model_name)
    if not _is_allowed_or_default(model_name, is_allowed=is_allowed):
        raise HTTPException(status_code=400, detail="Model is not in allowed model list.")

    installed_set = await _installed_name_set()
    if model_name not in installed_set:
        raise HTTPException(status_code=400, detail="Model is not installed. Install it first.")

    current = await repository.get_model_settings()
    next_router_model = (
        str(current["router_model"]).strip()
        if current is not None
        else router_model_env_default()
    )
    updated = await repository.upsert_model_settings(
        generation_model=model_name,
        router_model=next_router_model,
    )
    return {
        "generation_model": str(updated["generation_model"]),
        "router_model": str(updated["router_model"]),
        "source": "db",
    }


async def select_router_model(model_name: str) -> dict:
    model_name = (model_name or "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="Model name is required.")

    is_allowed = await repository.is_allowed_model(model_name)
    if not _is_allowed_or_default(model_name, is_allowed=is_allowed):
        raise HTTPException(status_code=400, detail="Model is not in allowed model list.")

    installed_set = await _installed_name_set()
    if model_name not in installed_set:
        raise HTTPException(status_code=400, detail="Model is not installed. Install it first.")

    current = await repository.get_model_settings()
    next_generation_model = (
        str(current["generation_model"]).strip()
        if current is not None
        else generation_model_env_default()
    )
    updated = await repository.upsert_model_settings(
        generation_model=next_generation_model,
        router_model=model_name,
    )
    return {
        "generation_model": str(updated["generation_model"]),
        "router_model": str(updated["router_model"]),
        "source": "db",
    }


async def select_active_model(model_name: str) -> dict:
    # Backward-compatible alias: "active" means generation model.
    updated = await select_generation_model(model_name)
    return {
        "model": str(updated["generation_model"]),
        "source": str(updated["source"]),
        "is_installed": True,
    }


async def pull_model(model_name: str) -> dict:
    model_name = (model_name or "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="Model name is required.")

    is_allowed = await repository.is_allowed_model(model_name)
    if not _is_allowed_or_default(model_name, is_allowed=is_allowed):
        raise HTTPException(status_code=400, detail="Model is not in allowed model list.")

    base_url = ollama_base_url()
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=600.0) as client:
            resp = await client.post(
                "/api/pull",
                json={"model": model_name, "stream": False},
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to call Ollama pull endpoint: {exc}") from exc

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama pull request failed with status {resp.status_code}: {resp.text[:300]}",
        )

    data: dict[str, Any] = resp.json()
    return {
        "model": model_name,
        "status": data.get("status") or "ok",
        "done": bool(data.get("done", False)),
    }
