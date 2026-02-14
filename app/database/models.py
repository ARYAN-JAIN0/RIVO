from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("idx_leads_status", "status"),
        Index("idx_leads_review_status", "review_status"),
        UniqueConstraint("tenant_id", "email", name="uq_leads_tenant_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    role = Column(String)
    company = Column(String)
    website = Column(String)
    location = Column(String)
    company_size = Column(String)
    industry = Column(String)
    verified_insight = Column(Text)
    negative_signals = Column(Text)
    status = Column(String, default="New")
    last_contacted = Column(DateTime)
    signal_score = Column(Integer)
    confidence_score = Column(Integer)
    review_status = Column(String, default="New")
    draft_message = Column(Text)
    source = Column(String, default="manual")
    last_reply_at = Column(DateTime)
    followup_count = Column(Integer, default=0)
    next_followup_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    deals = relationship("Deal", back_populates="lead")
    tenant = relationship("Tenant")


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        Index("idx_deals_stage", "stage"),
        Index("idx_deals_review_status", "review_status"),
        Index("idx_deals_tenant_stage", "tenant_id", "stage"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    company = Column(String)
    acv = Column(Integer)
    qualification_score = Column(Integer)
    stage = Column(String, default="Lead")
    status = Column(String, default="Open")
    deal_value = Column(Integer)
    probability = Column(Float, default=0.0)
    expected_close_date = Column(Date)
    margin = Column(Float)
    cost_estimate = Column(Integer, default=0)
    forecast_month = Column(String)
    segment_tag = Column(String, default="SMB")
    probability_breakdown = Column(JSON)
    probability_explanation = Column(Text)
    probability_confidence = Column(Integer)
    proposal_path = Column(String)
    proposal_version = Column(Integer, default=0)
    notes = Column(Text)
    review_status = Column(String, default="Pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="deals")
    tenant = relationship("Tenant")


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        Index("idx_contracts_status", "status"),
        Index("idx_contracts_review_status", "review_status"),
        UniqueConstraint("deal_id", name="uq_contracts_deal_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    contract_code = Column(String, unique=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    status = Column(String, default="Negotiating")
    contract_terms = Column(Text)
    negotiation_points = Column(Text)
    objections = Column(Text)
    proposed_solutions = Column(Text)
    signed_date = Column(DateTime)
    contract_value = Column(Integer)
    last_updated = Column(DateTime, default=datetime.utcnow)
    review_status = Column(String, default="Pending")

    deal = relationship("Deal")
    lead = relationship("Lead")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("idx_invoices_status", "status"),
        Index("idx_invoices_review_status", "review_status"),
        UniqueConstraint("contract_id", name="uq_invoices_contract_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    invoice_code = Column(String, unique=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    amount = Column(Integer)
    due_date = Column(Date)
    status = Column(String, default="Sent")
    days_overdue = Column(Integer, default=0)
    dunning_stage = Column(Integer, default=0)
    last_contact_date = Column(DateTime)
    payment_date = Column(DateTime)
    draft_message = Column(Text)
    confidence_score = Column(Integer)
    review_status = Column(String, default="New")

    contract = relationship("Contract")
    lead = relationship("Lead")


class ReviewAudit(Base):
    __tablename__ = "review_audit"
    __table_args__ = (Index("idx_review_audit_entity", "entity_type", "entity_id"),)

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    decision = Column(String, nullable=False)
    actor = Column(String, nullable=False, default="system")
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class EmailLog(Base):
    __tablename__ = "email_logs"
    __table_args__ = (
        Index("idx_email_logs_lead", "lead_id"),
        Index("idx_email_logs_status", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    message_type = Column(String, nullable=False, default="outbound")
    recipient_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    tracking_id = Column(String, unique=True)
    opened_at = Column(DateTime)
    clicked_at = Column(DateTime)
    status = Column(String, nullable=False, default="queued")
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("idx_agent_runs_agent_status", "agent_name", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    agent_name = Column(String, nullable=False)
    task_id = Column(String, unique=True)
    status = Column(String, nullable=False, default="queued")
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration_ms = Column(Integer)
    error_message = Column(Text)
    triggered_by = Column(String, default="api")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("agent_name", "template_key", name="uq_prompt_template_agent_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String, nullable=False)
    template_key = Column(String, nullable=False)
    template_body = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DealStageAudit(Base):
    __tablename__ = "deal_stage_audit"
    __table_args__ = (
        Index("idx_deal_stage_audit_deal", "deal_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    old_stage = Column(String, nullable=False)
    new_stage = Column(String, nullable=False)
    actor = Column(String, nullable=False, default="system")
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String, nullable=False, default="sales_agent")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_base.id"), nullable=False)
    vector = Column(Text, nullable=False)
    model = Column(String, nullable=False, default="hash-embedding-v1")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NegotiationMemory(Base):
    __tablename__ = "negotiation_memory"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    transcript = Column(Text, nullable=False)
    summary = Column(Text)
    objection_tags = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LLMLog(Base):
    __tablename__ = "llm_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    agent_name = Column(String, nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    prompt_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    confidence_score = Column(Integer)
    validation_status = Column(String, default="passed")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
