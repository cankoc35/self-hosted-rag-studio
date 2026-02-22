"""
Retrieval API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from auth import dependencies as auth_dependencies

from . import service

router = APIRouter()


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    limit: int = 10,
    current_user: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    results = await service.search_fts(q, user_id=int(current_user["id"]), limit=limit)
    return {"mode": "fts", "query": q, "results": results}


@router.get("/search/vector")
async def search_vector(
    q: str = Query(..., min_length=1),
    limit: int = 10,
    current_user: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    results = await service.search_vector(q, user_id=int(current_user["id"]), limit=limit)
    return {"mode": "vector", "query": q, "results": results}


@router.get("/search/hybrid")
async def search_hybrid(
    q: str = Query(..., min_length=1),
    limit: int = 10,
    full_text_candidate_limit: int = Query(50, alias="fts_k", ge=1),
    vector_candidate_limit: int = Query(50, alias="vec_k", ge=1),
    full_text_weight: float = Query(0.5, alias="weight_fts", ge=0.0),
    vector_weight: float = Query(0.5, alias="weight_vec", ge=0.0),
    rrf_rank_constant: int = Query(60, alias="rrf_k", ge=1),
    current_user: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    results = await service.search_hybrid(
        q,
        user_id=int(current_user["id"]),
        limit=limit,
        full_text_candidate_limit=full_text_candidate_limit,
        vector_candidate_limit=vector_candidate_limit,
        full_text_weight=full_text_weight,
        vector_weight=vector_weight,
        rrf_rank_constant=rrf_rank_constant,
    )
    return {
        "mode": "hybrid",
        "query": q,
        "params": {
            "full_text_candidate_limit": full_text_candidate_limit,
            "vector_candidate_limit": vector_candidate_limit,
            "full_text_weight": full_text_weight,
            "vector_weight": vector_weight,
            "rrf_rank_constant": rrf_rank_constant,
        },
        "results": results,
    }
