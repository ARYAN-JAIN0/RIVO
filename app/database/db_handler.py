# Database Handler (SQLAlchemy-based)
# FIXED VERSION - Addresses critical bugs from audit

import logging
from datetime import datetime
from typing import List, Optional, Union, Set

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database.db import SessionLocal
from app.database.models import Lead, Deal, Contract, Invoice

# Logger setup
logger = logging.getLogger(__name__)

# ==============================================================================
# LEADS - SDR AGENT
# ==============================================================================

def fetch_leads_by_status(status: str) -> List[Lead]:
    """
    Fetch leads by status. Uses title case to match application convention.
    
    FIXED: Status values are now consistently title case throughout codebase:
    - "New", "Contacted", "Qualified", etc.
    """
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
    """
    Update lead status. Only called on explicit transitions.
    
    FIXED: Uses title case status values consistently.
    """
    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.status = status
            lead.last_contacted = datetime.utcnow()
            session.commit()
            logger.info(f"Lead {lead_id} status updated to {status}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error updating lead status {lead_id}: {e}")
    finally:
        session.close()

def update_lead_signal_score(lead_id: int, score: int):
    """Update lead signal strength score (0-100)."""
    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.signal_score = score
            session.commit()
            logger.info(f"Lead {lead_id} signal score updated to {score}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error updating lead signal score {lead_id}: {e}")
    finally:
        session.close()

def save_draft(lead_id: int, draft_message: str, score: float, review_status: str):
    """
    Save email draft and review status WITHOUT changing lead status.
    
    CRITICAL FIX: Removed automatic status change to "Contacted".
    Lead status should ONLY be updated on explicit human approval via mark_review_decision().
    
    This preserves the human-in-loop gate: drafts must be reviewed and approved
    before the lead is marked as "Contacted".
    
    Args:
        lead_id: Lead ID
        draft_message: Generated email text
        score: Confidence score (0-100)
        review_status: Review state ("Approved", "Pending", "Rejected", "STRUCTURAL_FAILED")
    """
    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.draft_message = draft_message
            lead.confidence_score = score
            lead.review_status = review_status
            # CRITICAL FIX: Do NOT auto-set status to "Contacted" here
            # Status is only updated on explicit approval via mark_review_decision()
            session.commit()
            logger.info(f"Draft saved for lead {lead_id}, review_status={review_status}, score={score}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error saving draft for lead {lead_id}: {e}")
    finally:
        session.close()

def fetch_pending_reviews(include_structural_failed=False) -> List[Lead]:
    """
    Fetch leads pending human review.
    
    FIXED: Uses review_status field (not status field) to identify pending items.
    """
    session = SessionLocal()
    try:
        query = session.query(Lead)
        if include_structural_failed:
            query = query.filter(Lead.review_status.in_(["Pending", "STRUCTURAL_FAILED"]))
        else:
            query = query.filter(Lead.review_status == "Pending")
        results = query.all()
        logger.info(f"Found {len(results)} pending reviews (include_failed={include_structural_failed})")
        return results
    except SQLAlchemyError as e:
        logger.error(f"Error fetching pending reviews: {e}")
        return []
    finally:
        session.close()

def mark_review_decision(lead_id: int, decision: str, edited_email: str = None):
    """
    Record human review decision and update lead status accordingly.
    
    FIXED: This is the ONLY place where lead status transitions to "Contacted".
    Only on explicit "Approved" decision does the lead become contacted.
    
    Args:
        lead_id: Lead ID
        decision: "Approved", "Rejected", "BLOCKED", "SKIPPED"
        edited_email: Optional human-edited email text
    """
    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.review_status = decision
            if edited_email:
                lead.draft_message = edited_email
            
            # Only transition to "Contacted" on explicit approval
            if decision == "Approved":
                lead.status = "Contacted"
                lead.last_contacted = datetime.utcnow()
                logger.info(f"Lead {lead_id} approved and marked as Contacted")
            else:
                logger.info(f"Lead {lead_id} review decision: {decision}")
            
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking review decision for lead {lead_id}: {e}")
    finally:
        session.close()

# ==============================================================================
# DEALS - SALES AGENT
# ==============================================================================

def create_deal(lead_id: int, company: str, acv: int, qualification_score: int, notes: str = "", stage: str = "Qualified") -> int:
    """
    Create new deal from qualified lead.
    
    FIXED: Uses title case for stage values ("Qualified", "Proposal Sent", etc.)
    """
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
        logger.info(f"Deal {new_deal.id} created for lead {lead_id}, acv=${acv}")
        return new_deal.id
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error creating deal: {e}")
        raise
    finally:
        session.close()

def fetch_deals_by_status(stage: str) -> List[Deal]:
    """
    Fetch deals by stage.
    
    FIXED: Uses title case for stage values.
    """
    session = SessionLocal()
    try:
        deals = session.query(Deal).filter(Deal.stage == stage).all()
        logger.info(f"Found {len(deals)} deals with stage={stage}")
        return deals
    except SQLAlchemyError as e:
        logger.error(f"Error fetching deals by status {stage}: {e}")
        return []
    finally:
        session.close()

def update_deal_stage(deal_id: int, new_stage: str, notes: str = ""):
    """Update deal stage with optional notes."""
    session = SessionLocal()
    try:
        deal = session.query(Deal).filter(Deal.id == deal_id).first()
        if deal:
            deal.stage = new_stage
            deal.last_updated = datetime.utcnow()
            if notes:
                deal.notes = notes
            session.commit()
            logger.info(f"Deal {deal_id} stage updated to {new_stage}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error updating deal stage {deal_id}: {e}")
    finally:
        session.close()

def save_deal_review(deal_id: int, notes: str, score: int, review_status: str = "Pending"):
    """Save deal qualification review data."""
    session = SessionLocal()
    try:
        deal = session.query(Deal).filter(Deal.id == deal_id).first()
        if deal:
            deal.qualification_score = score
            deal.notes = notes
            deal.review_status = review_status
            deal.last_updated = datetime.utcnow()
            session.commit()
            logger.info(f"Deal {deal_id} review saved, score={score}, status={review_status}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error saving deal review {deal_id}: {e}")
    finally:
        session.close()

def fetch_pending_deal_reviews() -> List[Deal]:
    """
    Fetch deals pending human review.
    
    FIXED: Uses review_status field to identify pending items.
    """
    session = SessionLocal()
    try:
        deals = session.query(Deal).filter(Deal.review_status == "Pending").all()
        logger.info(f"Found {len(deals)} pending deal reviews")
        return deals
    except SQLAlchemyError as e:
        logger.error(f"Error fetching pending deal reviews: {e}")
        return []
    finally:
        session.close()

def mark_deal_decision(deal_id: int, decision: str):
    """Record human review decision for deal."""
    session = SessionLocal()
    try:
        deal = session.query(Deal).filter(Deal.id == deal_id).first()
        if deal:
            deal.review_status = decision
            if decision == "Approved":
                deal.stage = "Proposal Sent"
                logger.info(f"Deal {deal_id} approved and moved to Proposal Sent")
            else:
                logger.info(f"Deal {deal_id} review decision: {decision}")
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking deal decision {deal_id}: {e}")
    finally:
        session.close()

# ==============================================================================
# CONTRACTS - NEGOTIATION AGENT
# ==============================================================================

def create_contract(deal_id: int, lead_id: int, contract_terms: str, contract_value: int) -> int:
    """Create new contract from deal."""
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
        logger.info(f"Contract {new_contract.id} created for deal {deal_id}, value=${contract_value}")
        return new_contract.id
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error creating contract: {e}")
        raise
    finally:
        session.close()

def fetch_contracts_by_status(status: str) -> List[Contract]:
    """Fetch contracts by status."""
    session = SessionLocal()
    try:
        contracts = session.query(Contract).filter(Contract.status == status).all()
        logger.info(f"Found {len(contracts)} contracts with status={status}")
        return contracts
    except SQLAlchemyError as e:
        logger.error(f"Error fetching contracts by status {status}: {e}")
        return []
    finally:
        session.close()

def update_contract_negotiation(contract_id: int, objections: str, proposed_solutions: str, confidence_score: int):
    """Update contract with negotiation details."""
    session = SessionLocal()
    try:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.objections = objections
            contract.proposed_solutions = proposed_solutions
            contract.last_updated = datetime.utcnow()
            contract.review_status = "Auto-Approved" if confidence_score >= 85 else "Pending"
            session.commit()
            logger.info(f"Contract {contract_id} negotiation updated, confidence={confidence_score}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error updating contract negotiation {contract_id}: {e}")
    finally:
        session.close()

def mark_contract_signed(contract_id: int):
    """Mark contract as signed (final state)."""
    session = SessionLocal()
    try:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.status = "Signed"
            contract.signed_date = datetime.utcnow()
            contract.review_status = "Approved"
            session.commit()
            logger.info(f"Contract {contract_id} marked as signed")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking contract signed {contract_id}: {e}")
    finally:
        session.close()

def fetch_pending_contract_reviews() -> List[Contract]:
    """Fetch contracts pending human review."""
    session = SessionLocal()
    try:
        contracts = session.query(Contract).filter(Contract.review_status == "Pending").all()
        logger.info(f"Found {len(contracts)} pending contract reviews")
        return contracts
    except SQLAlchemyError as e:
        logger.error(f"Error fetching pending contract reviews: {e}")
        return []
    finally:
        session.close()

def mark_contract_decision(contract_id: int, decision: str):
    """Record human review decision for contract."""
    session = SessionLocal()
    try:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.review_status = decision
            if decision == "Approved":
                contract.status = "Signed"
                contract.signed_date = datetime.utcnow()
                logger.info(f"Contract {contract_id} approved and marked as signed")
            else:
                logger.info(f"Contract {contract_id} review decision: {decision}")
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking contract decision {contract_id}: {e}")
    finally:
        session.close()

# ==============================================================================
# INVOICES - FINANCE AGENT
# ==============================================================================

def create_invoice(contract_id: int, lead_id: int, amount: int, due_date: Union[str, datetime]) -> int:
    """
    Create new invoice for signed contract.
    
    CRITICAL FIX: Added deduplication check to prevent duplicate invoices
    for the same contract.
    """
    session = SessionLocal()
    try:
        # FIXED: Check if invoice already exists for this contract
        existing = session.query(Invoice).filter(Invoice.contract_id == contract_id).first()
        if existing:
            logger.warning(f"Invoice already exists for contract {contract_id}, returning existing invoice {existing.id}")
            return existing.id
        
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
        logger.info(f"Invoice {new_invoice.id} created for contract {contract_id}, amount=${amount}")
        return new_invoice.id
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error creating invoice: {e}")
        raise
    finally:
        session.close()

def fetch_invoices_by_status(status: str) -> List[Invoice]:
    """Fetch invoices by status."""
    session = SessionLocal()
    try:
        invoices = session.query(Invoice).filter(Invoice.status == status).all()
        logger.info(f"Found {len(invoices)} invoices with status={status}")
        return invoices
    except SQLAlchemyError as e:
        logger.error(f"Error fetching invoices by status {status}: {e}")
        return []
    finally:
        session.close()

def fetch_all_invoices() -> List[Invoice]:
    """Fetch all invoices."""
    session = SessionLocal()
    try:
        invoices = session.query(Invoice).all()
        logger.info(f"Found {len(invoices)} total invoices")
        return invoices
    except SQLAlchemyError as e:
        logger.error(f"Error fetching all invoices: {e}")
        return []
    finally:
        session.close()

def update_invoice_status(invoice_id: int, status: str, days_overdue: int = 0, dunning_stage: int = 0):
    """Update invoice status and overdue tracking."""
    session = SessionLocal()
    try:
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            invoice.status = status
            invoice.days_overdue = days_overdue
            invoice.dunning_stage = dunning_stage
            session.commit()
            logger.info(f"Invoice {invoice_id} status updated to {status}, overdue={days_overdue}d")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error updating invoice status {invoice_id}: {e}")
    finally:
        session.close()

def save_dunning_draft(invoice_id: int, draft_message: str, confidence_score: int):
    """Save dunning email draft for review."""
    session = SessionLocal()
    try:
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            invoice.draft_message = draft_message
            invoice.confidence_score = confidence_score
            invoice.review_status = "Auto-Approved" if confidence_score >= 85 else "Pending"
            invoice.last_contact_date = datetime.utcnow()
            session.commit()
            logger.info(f"Dunning draft saved for invoice {invoice_id}, confidence={confidence_score}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error saving dunning draft {invoice_id}: {e}")
    finally:
        session.close()

def mark_invoice_paid(invoice_id: int):
    """Mark invoice as paid (final state)."""
    session = SessionLocal()
    try:
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            invoice.status = "Paid"
            invoice.payment_date = datetime.utcnow()
            session.commit()
            logger.info(f"Invoice {invoice_id} marked as paid")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking invoice paid {invoice_id}: {e}")
    finally:
        session.close()

def fetch_pending_dunning_reviews() -> List[Invoice]:
    """Fetch invoices with pending dunning email reviews."""
    session = SessionLocal()
    try:
        invoices = session.query(Invoice).filter(Invoice.review_status == "Pending").all()
        logger.info(f"Found {len(invoices)} pending dunning reviews")
        return invoices
    except SQLAlchemyError as e:
        logger.error(f"Error fetching pending dunning reviews: {e}")
        return []
    finally:
        session.close()

def mark_dunning_decision(invoice_id: int, decision: str):
    """Record human review decision for dunning email."""
    session = SessionLocal()
    try:
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            invoice.review_status = decision
            if decision == "Approved":
                invoice.dunning_stage += 1
                invoice.last_contact_date = datetime.utcnow()
                logger.info(f"Dunning email approved for invoice {invoice_id}, stage={invoice.dunning_stage}")
            else:
                logger.info(f"Invoice {invoice_id} dunning decision: {decision}")
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error marking dunning decision {invoice_id}: {e}")
    finally:
        session.close()
