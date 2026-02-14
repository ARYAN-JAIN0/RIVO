"""Tenant-aware leads service facade for API and worker usage."""

from __future__ import annotations

from app.services.lead_service import LeadService


class LeadsService(LeadService):
    """Pluralized facade kept for target layout compatibility.

    Existing callers can import `LeadService` or `LeadsService` interchangeably
    during the migration window.
    """
