"""Contract model module."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, TenantScopedMixin
from app.models.enums import ContractStatus


class Contract(Base, AuditMixin, TenantScopedMixin):
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "deal_id", name="uq_contracts_tenant_deal"),
        Index("idx_contracts_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_code: Mapped[str | None] = mapped_column(String(64), unique=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="RESTRICT"), nullable=False)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[ContractStatus] = mapped_column(Enum(ContractStatus), default=ContractStatus.NEGOTIATING, nullable=False)
    contract_terms: Mapped[str | None] = mapped_column(Text)
    contract_value: Mapped[float | None] = mapped_column(Numeric(12, 2))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    deal = relationship("Deal")
    lead = relationship("Lead")
