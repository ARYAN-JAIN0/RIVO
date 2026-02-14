"""Invoice request/response schemas for API contracts."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class InvoiceCreateRequest(BaseModel):
    contract_id: int = Field(ge=1)
    lead_id: int = Field(ge=1)
    amount: int = Field(ge=0)
    due_date: date
    status: str | None = Field(default=None, min_length=2, max_length=40)
    dunning_stage: int = Field(default=0, ge=0)


class InvoiceStatusUpdateRequest(BaseModel):
    status: str = Field(min_length=2, max_length=40)
    days_overdue: int | None = Field(default=None, ge=0)
    dunning_stage: int | None = Field(default=None, ge=0)


class InvoiceDraftUpdateRequest(BaseModel):
    draft_message: str = Field(min_length=1, max_length=10000)
    confidence_score: int = Field(ge=0, le=100)


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_code: str | None = None
    contract_id: int
    lead_id: int
    amount: int | None = None
    due_date: date | None = None
    status: str
    days_overdue: int | None = None
    dunning_stage: int | None = None
    last_contact_date: datetime | None = None
    payment_date: datetime | None = None
    draft_message: str | None = None
    confidence_score: int | None = None
    review_status: str | None = None
