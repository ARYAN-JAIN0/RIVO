"""Invoice service for common invoice operations."""

from __future__ import annotations

from app.core.enums import InvoiceStatus
from app.database.models import Invoice
from app.services.base_service import BaseService


class InvoiceService(BaseService):
    """Service for managing invoices with deterministic status updates."""

    def validate(self) -> None:
        if self.db is None:
            raise ValueError("Database session is not initialized.")

    def get_invoice(self, invoice_id: int) -> Invoice | None:
        self.validate()
        return self.db.query(Invoice).filter(Invoice.id == invoice_id).first()

    def mark_paid(self, invoice_id: int) -> bool:
        self.validate()
        invoice = self.get_invoice(invoice_id)
        if invoice is None:
            return False
        invoice.status = InvoiceStatus.PAID.value
        self.commit()
        return True

