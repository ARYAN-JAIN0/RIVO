"""Deal model module."""

from __future__ import annotations

from sqlalchemy import Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, TenantScopedMixin
from app.models.enums import DealStage


class Deal(Base, AuditMixin, TenantScopedMixin):
    __tablename__ = "deals"
    __table_args__ = (
        Index("idx_deals_tenant_stage", "tenant_id", "stage"),
        Index("idx_deals_tenant_lead", "tenant_id", "lead_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255))
    acv: Mapped[float | None] = mapped_column(Numeric(12, 2))
    qualification_score: Mapped[int | None] = mapped_column(Integer)
    stage: Mapped[DealStage] = mapped_column(Enum(DealStage), default=DealStage.QUALIFIED, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    lead = relationship("Lead", back_populates="deals")
