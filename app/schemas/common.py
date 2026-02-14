"""Common schema module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class APIEnvelope(BaseModel):
    status: str = "ok"
    message: str | None = None


class Pagination(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ErrorEnvelope(BaseModel):
    status: str = "error"
    error_code: str
    detail: str
