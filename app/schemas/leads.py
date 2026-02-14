"""Lead request/response schemas for API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeadCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320)
    role: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    company_size: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=120)
    verified_insight: str | None = Field(default=None, max_length=2000)
    negative_signals: str | None = Field(default=None, max_length=2000)


class LeadStatusUpdateRequest(BaseModel):
    status: str = Field(min_length=2, max_length=40)


class LeadDraftUpdateRequest(BaseModel):
    draft: str = Field(min_length=1, max_length=10000)
    confidence: int = Field(ge=0, le=100)


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str | None = None
    company: str | None = None
    company_size: str | None = None
    industry: str | None = None
    verified_insight: str | None = None
    negative_signals: str | None = None
    status: str
    signal_score: int | None = None
    confidence_score: int | None = None
    review_status: str | None = None
    draft_message: str | None = None
    last_contacted: datetime | None = None
    created_at: datetime | None = None
