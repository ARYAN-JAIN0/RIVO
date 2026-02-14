"""Tenant-aware invoices service facade for API and worker usage."""

from __future__ import annotations

from app.services.invoice_service import InvoiceService


class InvoicesService(InvoiceService):
    """Pluralized facade kept for target layout compatibility.

    Existing callers can import `InvoiceService` or `InvoicesService`
    interchangeably during the migration window.
    """
