"""Deal request/response schemas for API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DealCreateRequest(BaseModel):
    lead_id: int = Field(ge=1)
    company: str | None = Field(default=None, max_length=255)
    acv: int = Field(ge=0)
    qualification_score: int = Field(ge=0, le=100)
    stage: str | None = Field(default=None, min_length=2, max_length=40)
    notes: str | None = Field(default=None, max_length=10000)
    review_status: str = Field(default="Pending", min_length=2, max_length=40)


class DealStageUpdateRequest(BaseModel):
    stage: str = Field(min_length=2, max_length=40)


class DealNotesUpdateRequest(BaseModel):
    notes: str = Field(min_length=1, max_length=10000)


class DealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    company: str | None = None
    acv: int | None = None
    qualification_score: int | None = None
    stage: str
    notes: str | None = None
    review_status: str | None = None
    created_at: datetime | None = None
    last_updated: datetime | None = None
