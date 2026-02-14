"""Tenant-aware invoices service facade for API and worker usage."""

from __future__ import annotations

from app.services.invoice_service import InvoiceService


class InvoicesService(InvoiceService):
    """Pluralized service name used by the target backend layout."""

