# Database Handler (SQLAlchemy-based)
# Replaces CSV handling with Postgres/SQLAlchemy ORM

import logging
from datetime import datetime
from typing import List, Optional, Union

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database.db import SessionLocal
from app.database.models import Lead, Deal, Contract, Invoice

# Logger setup
logger = logging.getLogger(__name__)

# ==============================================================================
# PHASE-2 FUNCTIONS (UNCHANGED - DO NOT MODIFY)
# ==============================================================================

def fetch_leads_by_status(status: str) -> List[Lead]:
    session = SessionLocal()
    try:
        leads = session.query(Lead).filter(Lead.status == status).all()
        return leads
    except SQLAlchemyError as e:
        logger.error(f"Error fetching leads by status {status}: {e}")
        return []
    finally:
        session.close()

def update_lead_status(lead_id: int, status: str):
    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.status = status
            lead.last_contacted = datetime.utcnow()
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error updating lead status {lead_id}: {e}")
    finally:
        session.close()

def save_draft(lead_id: int, draft_message: str, score: float, status: str):
    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.draft_message = draft_message
            lead.confidence_score = score
            lead.review_status = status
            # Auto-update status to Contacted if saving draft? 
            # Original logic implied this. Keeping consistent.
            lead.status = "Contacted"
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error saving draft for lead {lead_id}: {e}")
    finally:
        session.close()

def fetch_pending_reviews(include_structural_failed=False) -> List[Lead]:
    session = SessionLocal()
    try:
        query = session.query(Lead)
        if include_structural_failed:
             query = query.filter(Lead.review_status.in_(["Pending", "STRUCTURAL_FAILED"]))
        else:
             query = query.filter(Lead.review_status == "Pending")
        return query.all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching pending reviews: {e}")
        return []
    finally:
        session.close()

def mark_review_decision(lead_id: int, decision: str, edited_email: str = None):
    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.review_status = decision
            if edited_email:
                lead.draft_message = edited_email
            
            if decision == "Approved":
                lead.status = "Contacted"
                lead.last_contacted = datetime.utcnow()
            
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking review decision for lead {lead_id}: {e}")
    finally:
        session.close()

# ==============================================================================
# DEALS
# ==============================================================================

def create_deal(lead_id: int, company: str, acv: int, qualification_score: int, notes: str = "", stage: str = "qualified") -> int:
    session = SessionLocal()
    try:
        new_deal = Deal(
            lead_id=lead_id,
            company=company,
            acv=acv,
            qualification_score=qualification_score,
            stage=stage,
            notes=notes,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
            review_status="Pending"
        )
        session.add(new_deal)
        session.commit()
        session.refresh(new_deal)
        return new_deal.id
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error creating deal: {e}")
        raise
    finally:
        session.close()

def fetch_deals_by_status(status: str) -> List[Deal]:
    session = SessionLocal()
    try:
        return session.query(Deal).filter(Deal.stage == status).all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching deals by status {status}: {e}")
        return []
    finally:
        session.close()

def update_deal_stage(deal_id: int, new_stage: str, notes: str = ""):
    session = SessionLocal()
    try:
        deal = session.query(Deal).filter(Deal.id == deal_id).first()
        if deal:
            deal.stage = new_stage
            deal.last_updated = datetime.utcnow()
            if notes:
                deal.notes = notes
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error updating deal stage {deal_id}: {e}")
    finally:
        session.close()

def save_deal_review(deal_id: int, notes: str, score: int, review_status: str = "Pending"):
    session = SessionLocal()
    try:
        deal = session.query(Deal).filter(Deal.id == deal_id).first()
        if deal:
            deal.qualification_score = score
            deal.notes = notes
            deal.review_status = review_status
            deal.last_updated = datetime.utcnow()
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error saving deal review {deal_id}: {e}")
    finally:
        session.close()

def fetch_pending_deal_reviews() -> List[Deal]:
    session = SessionLocal()
    try:
        return session.query(Deal).filter(Deal.review_status == "Pending").all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching pending deal reviews: {e}")
        return []
    finally:
        session.close()

def mark_deal_decision(deal_id: int, decision: str):
    session = SessionLocal()
    try:
        deal = session.query(Deal).filter(Deal.id == deal_id).first()
        if deal:
            deal.review_status = decision
            if decision == "Approved":
                deal.stage = "Proposal Sent"
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking deal decision {deal_id}: {e}")
    finally:
        session.close()

# ==============================================================================
# CONTRACTS
# ==============================================================================

def create_contract(deal_id: int, lead_id: int, contract_terms: str, contract_value: int) -> int:
    session = SessionLocal()
    try:
        new_contract = Contract(
            deal_id=deal_id,
            lead_id=lead_id,
            status="Negotiating",
            contract_terms=contract_terms,
            contract_value=contract_value,
            last_updated=datetime.utcnow(),
            review_status="Pending"
        )
        session.add(new_contract)
        session.commit()
        session.refresh(new_contract)
        return new_contract.id
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error creating contract: {e}")
        raise
    finally:
        session.close()

def fetch_contracts_by_status(status: str) -> List[Contract]:
    session = SessionLocal()
    try:
        return session.query(Contract).filter(Contract.status == status).all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching contracts by status {status}: {e}")
        return []
    finally:
        session.close()

def update_contract_negotiation(contract_id: int, objections: str, proposed_solutions: str, confidence_score: int):
    session = SessionLocal()
    try:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.objections = objections
            contract.proposed_solutions = proposed_solutions
            contract.last_updated = datetime.utcnow()
            contract.review_status = "Auto-Approved" if confidence_score >= 85 else "Pending"
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error updating contract negotiation {contract_id}: {e}")
    finally:
        session.close()

def mark_contract_signed(contract_id: int):
    session = SessionLocal()
    try:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.status = "Signed"
            contract.signed_date = datetime.utcnow()
            contract.review_status = "Approved"
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking contract signed {contract_id}: {e}")
    finally:
        session.close()

def fetch_pending_contract_reviews() -> List[Contract]:
    session = SessionLocal()
    try:
        return session.query(Contract).filter(Contract.review_status == "Pending").all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching pending contract reviews: {e}")
        return []
    finally:
        session.close()

def mark_contract_decision(contract_id: int, decision: str):
    session = SessionLocal()
    try:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.review_status = decision
            if decision == "Approved":
                contract.status = "Signed"
                contract.signed_date = datetime.utcnow()
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking contract decision {contract_id}: {e}")
    finally:
        session.close()

# ==============================================================================
# INVOICES
# ==============================================================================

def create_invoice(contract_id: int, lead_id: int, amount: int, due_date: Union[str, datetime]) -> int:
    session = SessionLocal()
    try:
        if isinstance(due_date, str):
            due_date_obj = datetime.strptime(due_date, "%Y-%m-%d").date()
        else:
            due_date_obj = due_date
            
        new_invoice = Invoice(
            contract_id=contract_id,
            lead_id=lead_id,
            amount=amount,
            due_date=due_date_obj,
            status="Sent",
            days_overdue=0,
            dunning_stage=0,
            last_contact_date=datetime.utcnow(),
            review_status="New"
        )
        session.add(new_invoice)
        session.commit()
        session.refresh(new_invoice)
        return new_invoice.id
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error creating invoice: {e}")
        raise
    finally:
        session.close()

def fetch_invoices_by_status(status: str) -> List[Invoice]:
    session = SessionLocal()
    try:
        return session.query(Invoice).filter(Invoice.status == status).all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching invoices by status {status}: {e}")
        return []
    finally:
        session.close()

def fetch_all_invoices() -> List[Invoice]:
     session = SessionLocal()
     try:
         return session.query(Invoice).all()
     except SQLAlchemyError as e:
         logger.error(f"Error fetching all invoices: {e}")
         return []
     finally:
         session.close()

# Legacy support renaming
_load_invoices_df = fetch_all_invoices 

def update_invoice_status(invoice_id: int, status: str, days_overdue: int = 0, dunning_stage: int = 0):
    session = SessionLocal()
    try:
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            invoice.status = status
            invoice.days_overdue = days_overdue
            invoice.dunning_stage = dunning_stage
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error updating invoice status {invoice_id}: {e}")
    finally:
        session.close()

def save_dunning_draft(invoice_id: int, draft_message: str, confidence_score: int):
    session = SessionLocal()
    try:
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            invoice.draft_message = draft_message
            invoice.confidence_score = confidence_score
            invoice.review_status = "Auto-Approved" if confidence_score >= 85 else "Pending"
            invoice.last_contact_date = datetime.utcnow()
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error saving dunning draft {invoice_id}: {e}")
    finally:
        session.close()

def mark_invoice_paid(invoice_id: int):
    session = SessionLocal()
    try:
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            invoice.status = "Paid"
            invoice.payment_date = datetime.utcnow()
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking invoice paid {invoice_id}: {e}")
    finally:
        session.close()

def fetch_pending_dunning_reviews() -> List[Invoice]:
    session = SessionLocal()
    try:
        return session.query(Invoice).filter(Invoice.review_status == "Pending").all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching pending dunning reviews: {e}")
        return []
    finally:
        session.close()

def mark_dunning_decision(invoice_id: int, decision: str):
    session = SessionLocal()
    try:
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            invoice.review_status = decision
            if decision == "Approved":
                invoice.dunning_stage += 1
                invoice.last_contact_date = datetime.utcnow()
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking dunning decision {invoice_id}: {e}")
    finally:
        session.close()


