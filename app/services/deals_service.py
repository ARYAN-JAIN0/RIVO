"""Tenant-aware deals service facade for API and worker usage."""

from __future__ import annotations

from app.services.deal_service import DealService


class DealsService(DealService):
    """Pluralized facade kept for target layout compatibility.

    Existing callers can import `DealService` or `DealsService` interchangeably
    during the migration window.
    """
