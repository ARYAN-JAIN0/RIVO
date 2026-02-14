"""Pipeline stage model module."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantScopedMixin


class PipelineStage(Base, AuditMixin, TenantScopedMixin):
    __tablename__ = "pipeline_stages"
    __table_args__ = (Index("idx_pipeline_stage_tenant_entity", "tenant_id", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    change_reason: Mapped[str | None] = mapped_column(Text)
