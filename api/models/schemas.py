"""
Pydantic schemas for model-management endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PullModelRequest(BaseModel):
    model: str = Field(..., min_length=1, max_length=200)


class SelectModelRequest(BaseModel):
    model: str = Field(..., min_length=1, max_length=200)


class SelectActiveModelRequest(SelectModelRequest):
    """
    Backward-compatible alias schema for generation model selection.
    """
