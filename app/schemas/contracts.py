"""Contract request/response schemas for API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContractCreateRequest(BaseModel):
    deal_id: int = Field(ge=1)
    lead_id: int = Field(ge=1)
    contract_terms: str = Field(min_length=1, max_length=20000)
    contract_value: int = Field(ge=0)
    status: str | None = Field(default=None, min_length=2, max_length=40)
    review_status: str = Field(default="Pending", min_length=2, max_length=40)


class ContractStatusUpdateRequest(BaseModel):
    status: str = Field(min_length=2, max_length=40)


class ContractNegotiationUpdateRequest(BaseModel):
    objections: str | None = Field(default=None, max_length=10000)
    proposed_solutions: str | None = Field(default=None, max_length=10000)
    confidence_score: int | None = Field(default=None, ge=0, le=100)


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_code: str | None = None
    deal_id: int
    lead_id: int
    status: str
    contract_terms: str | None = None
    negotiation_points: str | None = None
    objections: str | None = None
    proposed_solutions: str | None = None
    signed_date: datetime | None = None
    contract_value: int | None = None
    last_updated: datetime | None = None
    review_status: str | None = None
