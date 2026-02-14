"""Tenant-aware leads service facade for API and worker usage."""

from __future__ import annotations

from app.services.lead_service import LeadService


class LeadsService(LeadService):
    """Pluralized service name used by the target backend layout."""

