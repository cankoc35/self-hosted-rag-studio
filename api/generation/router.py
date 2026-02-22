"""
Generation API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from auth import dependencies as auth_dependencies
from . import service

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    full_text_candidate_limit: int = Field(default=50, ge=1)
    vector_candidate_limit: int = Field(default=50, ge=1)
    full_text_weight: float = Field(default=0.5, ge=0.0)
    vector_weight: float = Field(default=0.5, ge=0.0)
    rrf_rank_constant: int = Field(default=60, ge=1)
    debug: bool = False
    conversation_id: str | None = Field(default=None, min_length=1)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    return await service.chat(
        request.question,
        user_id=int(current_user["id"]),
        top_k=request.top_k,
        full_text_candidate_limit=request.full_text_candidate_limit,
        vector_candidate_limit=request.vector_candidate_limit,
        full_text_weight=request.full_text_weight,
        vector_weight=request.vector_weight,
        rrf_rank_constant=request.rrf_rank_constant,
        debug=request.debug,
        conversation_id=request.conversation_id,
    )


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str = Query(default="", max_length=500),
    similarity_threshold: float = Query(default=0.2, ge=0.0, le=1.0),
    current_user: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    return await service.list_conversations(
        user_id=int(current_user["id"]),
        limit=limit,
        offset=offset,
        search_query=q,
        similarity_threshold=similarity_threshold,
    )


@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(
    conversation_id: str,
    limit: int = 50,
    current_user: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    return await service.get_conversation_messages(
        conversation_id,
        user_id=int(current_user["id"]),
        limit=limit,
    )
