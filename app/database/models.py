from sqlalchemy import Column, Integer, String, Text, ForeignKey, Date, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class Lead(Base):
    __tablename__ = "leads"

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

    confidence_score = Column(Integer)
    review_status = Column(String)
    draft_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    deals = relationship("Deal", back_populates="lead")


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)

    lead_id = Column(Integer, ForeignKey("leads.id"))
    company = Column(String)

    acv = Column(Integer)
    qualification_score = Column(Integer)

    stage = Column(String)
    notes = Column(Text)

    review_status = Column(String)

    created_at = Column(DateTime)
    last_updated = Column(DateTime)

    lead = relationship("Lead")


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)

    contract_code = Column(String, unique=True)

    deal_id = Column(Integer, ForeignKey("deals.id"))

    lead_id = Column(Integer, ForeignKey("leads.id"))

    status = Column(String)

    contract_terms = Column(Text)
    negotiation_points = Column(Text)
    objections = Column(Text)
    proposed_solutions = Column(Text)

    signed_date = Column(DateTime)
    contract_value = Column(Integer)

    last_updated = Column(DateTime)
    review_status = Column(String)

    deal = relationship("Deal")
    lead = relationship("Lead")

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)

    invoice_code = Column(String, unique=True)

    contract_id = Column(Integer, ForeignKey("contracts.id"))
    lead_id = Column(Integer, ForeignKey("leads.id"))

    amount = Column(Integer)

    due_date = Column(Date)

    status = Column(String)
    days_overdue = Column(Integer)
    dunning_stage = Column(Integer)

    last_contact_date = Column(DateTime)
    payment_date = Column(DateTime)

    draft_message = Column(Text)
    confidence_score = Column(Integer)
    review_status = Column(String)

    contract = relationship("Contract")
    lead = relationship("Lead")
