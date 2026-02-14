"""Prompt schema module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PromptUpdateRequest(BaseModel):
    template: str = Field(min_length=1, max_length=20000)
    updated_by: str = Field(default="admin", min_length=2, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)


class PromptUpdateResponse(BaseModel):
    prompt_key: str
    updated_by: str
    updated: bool
