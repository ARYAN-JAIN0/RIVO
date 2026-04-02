"""Canonical enum values for the tenant-aware schema.

⚠️ DEPRECATED: This module is NOT connected to Alembic migrations.
Use app/core/enums.py instead for production code.
"""

from __future__ import annotations

import enum
import warnings

# Emit deprecation warning when this module is imported
warnings.warn(
    "app.models.enums is deprecated and not connected to Alembic. "
    "Use app.core.enums instead.",
    DeprecationWarning,
    stacklevel=2,
)


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
