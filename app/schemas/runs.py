"""Run schema module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RunTriggerRequest(BaseModel):
    tenant_id: int = Field(default=1, ge=1)
    user_id: int = Field(default=1, ge=1)
    payload: dict = Field(default_factory=dict)


class RunRetryRequest(BaseModel):
    tenant_id: int = Field(default=1, ge=1)
    user_id: int = Field(default=1, ge=1)


class ManualOverrideRequest(BaseModel):
    action: str = Field(min_length=2, max_length=120)
    reason: str = Field(min_length=3, max_length=2000)
    actor: str = Field(default="admin", min_length=2, max_length=120)


class RunResponse(BaseModel):
    run_id: str
    status: str
    retry_count: int | None = None
    error: str | None = None


class RunListItem(BaseModel):
    run_id: str
    agent_name: str
    status: str
    retry_count: int
    created_at: str
    finished_at: str | None = None

