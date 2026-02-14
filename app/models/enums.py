"""Canonical enum values for the tenant-aware schema."""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    SALES = "sales"
    SDR = "sdr"
    FINANCE = "finance"
    VIEWER = "viewer"


class LeadStatus(str, enum.Enum):
    NEW = "New"
    CONTACTED = "Contacted"
    QUALIFIED = "Qualified"
    DISQUALIFIED = "Disqualified"


class DealStage(str, enum.Enum):
    QUALIFIED = "Qualified"
    PROPOSAL_SENT = "Proposal Sent"
    WON = "Won"
    LOST = "Lost"


class ContractStatus(str, enum.Enum):
    NEGOTIATING = "Negotiating"
    SIGNED = "Signed"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class InvoiceStatus(str, enum.Enum):
    SENT = "Sent"
    PAID = "Paid"
    OVERDUE = "Overdue"
    VOID = "Void"


class RunStatus(str, enum.Enum):
    QUEUED = "Queued"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
