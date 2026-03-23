"""Pydantic schemas for LLM output validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EmailOutput(BaseModel):
    """Schema for email generation output."""
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body content")
    tone: str = Field(..., description="Tone of the email (professional, friendly, etc.)")


class StrategyOutput(BaseModel):
    """Schema for sales strategy output (reasoning)."""
    risk_level: str = Field(..., description="Risk level: low, medium, high")
    approach: str = Field(..., description="Recommended approach for the deal")
    key_points: list[str] = Field(default_factory=list, description="Key talking points")


class NegotiationOutput(BaseModel):
    """Schema for negotiation reasoning output."""
    counter_offer: float | None = Field(None, description="Counter offer amount if applicable")
    reasoning: str = Field(..., description="Reasoning for the negotiation stance")
    acceptable_range: tuple[float, float] | None = Field(None, description="Acceptable price range")


class FinanceOutput(BaseModel):
    """Schema for finance-related output."""
    invoice_amount: float = Field(..., description="Invoice amount")
    due_date: str = Field(..., description="Due date in YYYY-MM-DD format")
    payment_terms: str = Field(..., description="Payment terms")


class LeadScoreOutput(BaseModel):
    """Schema for lead scoring output."""
    score: int = Field(..., ge=0, le=100, description="Lead score 0-100")
    signal_score: int = Field(..., ge=0, le=100, description="Signal score 0-100")
    reasons: list[str] = Field(default_factory=list, description="Reasons for the score")
    icp_fit: bool = Field(..., description="Whether lead fits ICP")


class ProposalOutput(BaseModel):
    """Schema for sales proposal output."""
    title: str = Field(..., description="Proposal title")
    summary: str = Field(..., description="Executive summary")
    pricing: dict[str, Any] = Field(default_factory=dict, description="Pricing details")
    next_steps: list[str] = Field(default_factory=list, description="Recommended next steps")


# Schema registry for easy lookup
LLM_OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "email": EmailOutput,
    "strategy": StrategyOutput,
    "negotiation": NegotiationOutput,
    "finance": FinanceOutput,
    "lead_score": LeadScoreOutput,
    "proposal": ProposalOutput,
}


def get_schema(schema_name: str) -> type[BaseModel] | None:
    """Get schema by name."""
    return LLM_OUTPUT_SCHEMAS.get(schema_name)
