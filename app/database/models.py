from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    role = Column(String)
    company = Column(String)
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
    created_at = Column(DateTime, default=datetime.utcnow)

    deals = relationship("Deal", back_populates="lead")


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        Index("idx_deals_stage", "stage"),
        Index("idx_deals_review_status", "review_status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    company = Column(String)
    acv = Column(Integer)
    qualification_score = Column(Integer)
    stage = Column(String, default="Qualified")
    notes = Column(Text)
    review_status = Column(String, default="Pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="deals")


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

