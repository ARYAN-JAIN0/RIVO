"""Invoice service for common invoice operations."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.core.enums import InvoiceStatus
from app.database.models import Invoice
from app.services.base_service import BaseService


class InvoiceService(BaseService):
    """Service for invoice CRUD and dunning status transitions."""

    def _utcnow_naive(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def _to_date(self, due_date: str | date | datetime) -> date:
        if isinstance(due_date, date) and not isinstance(due_date, datetime):
            return due_date
        if isinstance(due_date, datetime):
            return due_date.date()
        return datetime.strptime(due_date, "%Y-%m-%d").date()

    def create_invoice(
        self,
        contract_id: int,
        lead_id: int,
        amount: int,
        due_date: str | date | datetime,
        status: str | None = None,
        dunning_stage: int = 0,
    ) -> Invoice:
        invoice = Invoice(
            contract_id=contract_id,
            lead_id=lead_id,
            amount=amount,
            due_date=self._to_date(due_date),
            status=status or InvoiceStatus.SENT.value,
            days_overdue=0,
            dunning_stage=dunning_stage,
        )
        self.db.add(invoice)
        self.commit()
        self.db.refresh(invoice)
        return invoice

    def get_invoice(self, invoice_id: int) -> Invoice | None:
        return self.db.query(Invoice).filter(Invoice.id == invoice_id).first()

    def list_by_status(self, status: str) -> list[Invoice]:
        return self.db.query(Invoice).filter(Invoice.status == status).all()

    def mark_paid(self, invoice_id: int) -> bool:
        invoice = self.get_invoice(invoice_id)
        if invoice is None:
            return False
        invoice.status = InvoiceStatus.PAID.value
        invoice.payment_date = self._utcnow_naive()
        self.commit()
        return True

    def update_status(
        self,
        invoice_id: int,
        status: str,
        days_overdue: int | None = None,
        dunning_stage: int | None = None,
    ) -> Invoice | None:
        invoice = self.get_invoice(invoice_id)
        if invoice is None:
            return None

        invoice.status = status
        if days_overdue is not None:
            invoice.days_overdue = days_overdue
        if dunning_stage is not None:
            invoice.dunning_stage = dunning_stage
        self.commit()
        self.db.refresh(invoice)
        return invoice

    def update_draft(self, invoice_id: int, draft_message: str, confidence_score: int) -> Invoice | None:
        invoice = self.get_invoice(invoice_id)
        if invoice is None:
            return None
        invoice.draft_message = draft_message
        invoice.confidence_score = confidence_score
        self.commit()
        self.db.refresh(invoice)
        return invoice
