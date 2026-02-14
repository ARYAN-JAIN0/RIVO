"""Tenant-aware contracts service facade for API and worker usage."""

from __future__ import annotations

from app.services.contract_service import ContractService


class ContractsService(ContractService):
    """Pluralized service name used by the target backend layout."""

