"""Negotiation history model module."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantScopedMixin


class NegotiationHistory(Base, AuditMixin, TenantScopedMixin):
    __tablename__ = "negotiation_history"
    __table_args__ = (Index("idx_negotiation_history_tenant_contract", "tenant_id", "contract_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    objections: Mapped[str | None] = mapped_column(Text)
    proposed_solutions: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[int | None] = mapped_column(Integer)
