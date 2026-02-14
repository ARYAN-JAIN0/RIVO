"""Phase 1 target SQLAlchemy model blueprint for production multi-tenant RIVO.

This file is intentionally non-runtime and is used as an implementation-ready
reference for Phase 2+ migration work.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, declarative_base


Base = declarative_base()


class SoftDeleteAuditMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TenantScopedMixin:
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    SALES = "sales"
    SDR = "sdr"
    FINANCE = "finance"
    VIEWER = "viewer"


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"


class DealStage(str, enum.Enum):
    QUALIFIED = "qualified"
    PROPOSAL_SENT = "proposal_sent"
    WON = "won"
    LOST = "lost"


class ContractStatus(str, enum.Enum):
    NEGOTIATING = "negotiating"
    SIGNED = "signed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InvoiceStatus(str, enum.Enum):
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Tenant(Base, SoftDeleteAuditMixin):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class User(Base, SoftDeleteAuditMixin, TenantScopedMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        Index("idx_users_tenant_role", "tenant_id", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship()


class Lead(Base, SoftDeleteAuditMixin, TenantScopedMixin):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_leads_tenant_email"),
        UniqueConstraint("tenant_id", "id", name="uq_leads_tenant_id_id"),
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


class PipelineStage(Base, SoftDeleteAuditMixin, TenantScopedMixin):
    __tablename__ = "pipeline_stages"
    __table_args__ = (Index("idx_pipeline_stage_tenant_entity", "tenant_id", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    change_reason: Mapped[str | None] = mapped_column(Text)


class Deal(Base, SoftDeleteAuditMixin, TenantScopedMixin):
    __tablename__ = "deals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            ondelete="RESTRICT",
            name="fk_deals_tenant_lead",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_deals_tenant_id_id"),
        Index("idx_deals_tenant_stage", "tenant_id", "stage"),
        Index("idx_deals_tenant_lead", "tenant_id", "lead_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(Integer, nullable=False)
    company: Mapped[str | None] = mapped_column(String(255))
    acv: Mapped[float | None] = mapped_column(Numeric(12, 2))
    qualification_score: Mapped[int | None] = mapped_column(Integer)
    stage: Mapped[DealStage] = mapped_column(Enum(DealStage), default=DealStage.QUALIFIED, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    lead: Mapped["Lead"] = relationship()


class NegotiationHistory(Base, SoftDeleteAuditMixin, TenantScopedMixin):
    __tablename__ = "negotiation_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "contract_id"],
            ["contracts.tenant_id", "contracts.id"],
            ondelete="CASCADE",
            name="fk_negotiation_history_tenant_contract",
        ),
        Index("idx_negotiation_history_tenant_contract", "tenant_id", "contract_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(Integer, nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    objections: Mapped[str | None] = mapped_column(Text)
    proposed_solutions: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[int | None] = mapped_column(Integer)


class Contract(Base, SoftDeleteAuditMixin, TenantScopedMixin):
    __tablename__ = "contracts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "deal_id"],
            ["deals.tenant_id", "deals.id"],
            ondelete="RESTRICT",
            name="fk_contracts_tenant_deal",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            ondelete="RESTRICT",
            name="fk_contracts_tenant_lead",
        ),
        UniqueConstraint("tenant_id", "deal_id", name="uq_contracts_tenant_deal"),
        UniqueConstraint("tenant_id", "id", name="uq_contracts_tenant_id_id"),
        Index("idx_contracts_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_code: Mapped[str | None] = mapped_column(String(64), unique=True)
    deal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ContractStatus] = mapped_column(Enum(ContractStatus), default=ContractStatus.NEGOTIATING, nullable=False)
    contract_terms: Mapped[str | None] = mapped_column(Text)
    contract_value: Mapped[float | None] = mapped_column(Numeric(12, 2))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invoice(Base, SoftDeleteAuditMixin, TenantScopedMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "contract_id"],
            ["contracts.tenant_id", "contracts.id"],
            ondelete="RESTRICT",
            name="fk_invoices_tenant_contract",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            ondelete="RESTRICT",
            name="fk_invoices_tenant_lead",
        ),
        UniqueConstraint("tenant_id", "contract_id", name="uq_invoices_tenant_contract"),
        Index("idx_invoices_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_code: Mapped[str | None] = mapped_column(String(64), unique=True)
    contract_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.SENT, nullable=False)
    days_overdue: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dunning_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailLog(Base, SoftDeleteAuditMixin, TenantScopedMixin):
    __tablename__ = "email_logs"
    __table_args__ = (Index("idx_email_logs_tenant_entity", "tenant_id", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False, default="smtp")
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_preview: Mapped[str] = mapped_column(Text, nullable=False)
    send_status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


class AgentRun(Base, SoftDeleteAuditMixin, TenantScopedMixin):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("idx_agent_runs_tenant_status", "tenant_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.QUEUED, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_payload: Mapped[dict | None] = mapped_column(JSON)
    result_payload: Mapped[dict | None] = mapped_column(JSON)
    error_payload: Mapped[dict | None] = mapped_column(JSON)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class LLMLog(Base, SoftDeleteAuditMixin, TenantScopedMixin):
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
