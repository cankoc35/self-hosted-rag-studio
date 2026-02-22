"""
Model-management API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from auth import dependencies as auth_dependencies

from . import schemas, service

router = APIRouter()


@router.get("/models/available")
async def get_available_models(
    q: str = Query(default="", max_length=500),
    similarity_threshold: float = Query(default=0.2, ge=0.0, le=1.0),
    _: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    rows = await service.available_models(
        search_query=q,
        similarity_threshold=similarity_threshold,
    )
    return {"models": rows, "count": len(rows)}


@router.get("/models/installed")
async def get_installed_models(
    _: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    rows = await service.installed_models()
    return {"models": rows, "count": len(rows)}


@router.get("/models/config")
async def get_model_config(
    _: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    return await service.model_config()


@router.get("/models/active")
async def get_active_model(
    _: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    return await service.active_model()


@router.post("/models/generation")
async def set_generation_model(
    request: schemas.SelectModelRequest,
    _: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    return await service.select_generation_model(request.model)


@router.post("/models/router")
async def set_router_model(
    request: schemas.SelectModelRequest,
    _: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    return await service.select_router_model(request.model)


@router.post("/models/active")
async def set_active_model(
    request: schemas.SelectActiveModelRequest,
    _: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    return await service.select_active_model(request.model)


@router.post("/models/pull")
async def pull_model(
    request: schemas.PullModelRequest,
    _: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    result = await service.pull_model(request.model)
    return result
