"""Lead model module."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, TenantScopedMixin
from app.models.enums import LeadStatus


class Lead(Base, AuditMixin, TenantScopedMixin):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_leads_tenant_email"),
        Index("idx_leads_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    company_size: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(120))
    verified_insight: Mapped[str | None] = mapped_column(Text)
    negative_signals: Mapped[str | None] = mapped_column(Text)
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.NEW, nullable=False)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signal_score: Mapped[int | None] = mapped_column(Integer)
    confidence_score: Mapped[int | None] = mapped_column(Integer)

    deals = relationship("Deal", back_populates="lead")
