"""Tenant-aware deals service facade for API and worker usage."""

from __future__ import annotations

from app.services.deal_service import DealService


class DealsService(DealService):
    """Pluralized service name used by the target backend layout."""

