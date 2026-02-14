"""Invoice model module."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, TenantScopedMixin
from app.models.enums import InvoiceStatus


class Invoice(Base, AuditMixin, TenantScopedMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "contract_id", name="uq_invoices_tenant_contract"),
        Index("idx_invoices_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_code: Mapped[str | None] = mapped_column(String(64), unique=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False)
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.SENT, nullable=False)
    days_overdue: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dunning_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    contract = relationship("Contract")
    lead = relationship("Lead")
