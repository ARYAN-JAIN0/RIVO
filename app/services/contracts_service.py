"""Tenant-aware contracts service facade for API and worker usage."""

from __future__ import annotations

from app.services.contract_service import ContractService


class ContractsService(ContractService):
    """Pluralized facade kept for target layout compatibility.

    Existing callers can import `ContractService` or `ContractsService`
    interchangeably during the migration window.
    """
