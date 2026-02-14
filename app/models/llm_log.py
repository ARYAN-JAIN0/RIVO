"""LLM log model module."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantScopedMixin


class LLMLog(Base, AuditMixin, TenantScopedMixin):
    __tablename__ = "llm_logs"
    __table_args__ = (Index("idx_llm_logs_tenant_model", "tenant_id", "model_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"))
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_template_key: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    token_usage_in: Mapped[int | None] = mapped_column(Integer)
    token_usage_out: Mapped[int | None] = mapped_column(Integer)
    confidence_score: Mapped[int | None] = mapped_column(Integer)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
