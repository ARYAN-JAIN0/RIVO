"""Pydantic schema package for API contracts."""

from app.schemas.auth import LoginRequest, RefreshRequest, TokenClaims, TokenResponse
from app.schemas.common import APIEnvelope, ErrorEnvelope, Pagination
from app.schemas.contracts import (
    ContractCreateRequest,
    ContractNegotiationUpdateRequest,
    ContractResponse,
    ContractStatusUpdateRequest,
)
from app.schemas.deals import DealCreateRequest, DealNotesUpdateRequest, DealResponse, DealStageUpdateRequest
from app.schemas.invoices import (
    InvoiceCreateRequest,
    InvoiceDraftUpdateRequest,
    InvoiceResponse,
    InvoiceStatusUpdateRequest,
)
from app.schemas.leads import LeadCreateRequest, LeadDraftUpdateRequest, LeadResponse, LeadStatusUpdateRequest
from app.schemas.prompts import PromptUpdateRequest, PromptUpdateResponse
from app.schemas.runs import (
    ManualOverrideRequest,
    RunListItem,
    RunResponse,
    RunRetryRequest,
    RunTriggerRequest,
)

__all__ = [
    "APIEnvelope",
    "ContractCreateRequest",
    "ContractNegotiationUpdateRequest",
    "ContractResponse",
    "ContractStatusUpdateRequest",
    "DealCreateRequest",
    "DealNotesUpdateRequest",
    "DealResponse",
    "DealStageUpdateRequest",
    "ErrorEnvelope",
    "InvoiceCreateRequest",
    "InvoiceDraftUpdateRequest",
    "InvoiceResponse",
    "InvoiceStatusUpdateRequest",
    "LeadCreateRequest",
    "LeadDraftUpdateRequest",
    "LeadResponse",
    "LeadStatusUpdateRequest",
    "LoginRequest",
    "ManualOverrideRequest",
    "Pagination",
    "PromptUpdateRequest",
    "PromptUpdateResponse",
    "RefreshRequest",
    "RunListItem",
    "RunResponse",
    "RunRetryRequest",
    "RunTriggerRequest",
    "TokenClaims",
    "TokenResponse",
]
