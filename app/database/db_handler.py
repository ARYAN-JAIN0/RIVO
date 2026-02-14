"""Database data-access layer with explicit review-gate semantics."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Union

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.enums import (
    ContractStatus,
    DealStage,
    InvoiceStatus,
    LeadStatus,
    ReviewStatus,
)
from app.database.db import get_db_session
from app.database.models import AgentRun, Contract, Deal, EmailLog, Invoice, LLMLog, Lead, PromptTemplate, ReviewAudit, Tenant
from utils.validators import sanitize_text

logger = logging.getLogger(__name__)


def _audit_review(entity_type: str, entity_id: int, decision: str, notes: str = "", actor: str = "system") -> None:
    try:
        with get_db_session() as session:
            audit = ReviewAudit(
                entity_type=entity_type,
                entity_id=entity_id,
                decision=decision,
                actor=actor,
                notes=sanitize_text(notes, max_len=4000),
            )
            session.add(audit)
            session.commit()
    except SQLAlchemyError:
        logger.exception("review_audit.write_failed", extra={"event": "review_audit.write_failed"})


# ==============================================================================
# LEADS - SDR AGENT
# ==============================================================================


def fetch_leads_by_status(status: str) -> List[Lead]:
    with get_db_session() as session:
        try:
            return session.query(Lead).filter(Lead.status == status).all()
        except SQLAlchemyError:
            logger.exception("db.fetch_leads_by_status.failed", extra={"event": "db.fetch_leads_by_status.failed"})
            return []


def update_lead_status(lead_id: int, status: str) -> None:
    with get_db_session() as session:
        try:
            lead = session.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return
            lead.status = status
            if status == LeadStatus.CONTACTED.value:
                lead.last_contacted = datetime.utcnow()
            session.commit()
            logger.info(
                "lead.status.updated",
                extra={"event": "lead.status.updated", "lead_id": lead_id, "status": status},
            )
        except SQLAlchemyError:
            session.rollback()
            logger.exception("lead.status.update_failed", extra={"event": "lead.status.update_failed", "lead_id": lead_id})


def update_lead_signal_score(lead_id: int, score: int) -> None:
    with get_db_session() as session:
        try:
            lead = session.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return
            lead.signal_score = score
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("lead.signal_score.update_failed", extra={"event": "lead.signal_score.update_failed", "lead_id": lead_id})


def save_draft(lead_id: int, draft_message: str, score: float, review_status: str) -> None:
    """
    Save SDR draft without modifying lead progression status.

    Lead progression must only move to Contacted through mark_review_decision.
    """
    with get_db_session() as session:
        try:
            lead = session.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return

            lead.draft_message = sanitize_text(draft_message)
            lead.confidence_score = int(score)
            lead.review_status = review_status
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("lead.draft.save_failed", extra={"event": "lead.draft.save_failed", "lead_id": lead_id})


def fetch_pending_reviews(include_structural_failed: bool = False) -> List[Lead]:
    with get_db_session() as session:
        try:
            query = session.query(Lead)
            if include_structural_failed:
                query = query.filter(Lead.review_status.in_([ReviewStatus.PENDING.value, ReviewStatus.STRUCTURAL_FAILED.value]))
            else:
                query = query.filter(Lead.review_status == ReviewStatus.PENDING.value)
            return query.all()
        except SQLAlchemyError:
            logger.exception("lead.pending_reviews.fetch_failed", extra={"event": "lead.pending_reviews.fetch_failed"})
            return []


def mark_review_decision(lead_id: int, decision: str, edited_email: str | None = None, actor: str = "human") -> None:
    with get_db_session() as session:
        try:
            lead = session.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return

            if edited_email is not None:
                lead.draft_message = sanitize_text(edited_email)
            lead.review_status = decision

            if decision == ReviewStatus.APPROVED.value:
                lead.status = LeadStatus.CONTACTED.value
                lead.last_contacted = datetime.utcnow()

            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("lead.review_decision.failed", extra={"event": "lead.review_decision.failed", "lead_id": lead_id})
            return

    _audit_review("lead", lead_id, decision, actor=actor)


# ==============================================================================
# DEALS - SALES AGENT
# ==============================================================================


def create_deal(
    lead_id: int,
    company: str,
    acv: int,
    qualification_score: int,
    notes: str = "",
    stage: str = DealStage.QUALIFIED.value,
) -> int:
    with get_db_session() as session:
        try:
            new_deal = Deal(
                lead_id=lead_id,
                company=sanitize_text(company, max_len=300),
                acv=acv,
                qualification_score=qualification_score,
                stage=stage,
                notes=sanitize_text(notes, max_len=10000),
                created_at=datetime.utcnow(),
                last_updated=datetime.utcnow(),
                review_status=ReviewStatus.PENDING.value,
            )
            session.add(new_deal)
            session.commit()
            session.refresh(new_deal)
            return new_deal.id
        except SQLAlchemyError:
            session.rollback()
            logger.exception("deal.create.failed", extra={"event": "deal.create.failed", "lead_id": lead_id})
            raise


def fetch_deals_by_status(stage: str) -> List[Deal]:
    with get_db_session() as session:
        try:
            return session.query(Deal).filter(Deal.stage == stage).all()
        except SQLAlchemyError:
            logger.exception("deal.fetch_by_stage.failed", extra={"event": "deal.fetch_by_stage.failed", "stage": stage})
            return []


def update_deal_stage(deal_id: int, new_stage: str, notes: str = "") -> None:
    with get_db_session() as session:
        try:
            deal = session.query(Deal).filter(Deal.id == deal_id).first()
            if not deal:
                return
            deal.stage = new_stage
            deal.last_updated = datetime.utcnow()
            if notes:
                deal.notes = sanitize_text(notes, max_len=10000)
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("deal.stage.update_failed", extra={"event": "deal.stage.update_failed", "deal_id": deal_id})


def save_deal_review(deal_id: int, notes: str, score: int, review_status: str = ReviewStatus.PENDING.value) -> None:
    with get_db_session() as session:
        try:
            deal = session.query(Deal).filter(Deal.id == deal_id).first()
            if not deal:
                return
            deal.qualification_score = score
            deal.notes = sanitize_text(notes, max_len=10000)
            deal.review_status = review_status
            deal.last_updated = datetime.utcnow()
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("deal.review.save_failed", extra={"event": "deal.review.save_failed", "deal_id": deal_id})


def fetch_pending_deal_reviews() -> List[Deal]:
    with get_db_session() as session:
        try:
            return session.query(Deal).filter(Deal.review_status == ReviewStatus.PENDING.value).all()
        except SQLAlchemyError:
            logger.exception("deal.pending_reviews.fetch_failed", extra={"event": "deal.pending_reviews.fetch_failed"})
            return []


def mark_deal_decision(deal_id: int, decision: str, actor: str = "human") -> None:
    with get_db_session() as session:
        try:
            deal = session.query(Deal).filter(Deal.id == deal_id).first()
            if not deal:
                return
            deal.review_status = decision
            if decision == ReviewStatus.APPROVED.value:
                deal.stage = DealStage.PROPOSAL_SENT.value
            deal.last_updated = datetime.utcnow()
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("deal.review_decision.failed", extra={"event": "deal.review_decision.failed", "deal_id": deal_id})
            return

    _audit_review("deal", deal_id, decision, actor=actor)


# ==============================================================================
# CONTRACTS - NEGOTIATION AGENT
# ==============================================================================


def create_contract(deal_id: int, lead_id: int, contract_terms: str, contract_value: int) -> int:
    with get_db_session() as session:
        try:
            existing = session.query(Contract).filter(Contract.deal_id == deal_id).first()
            if existing:
                return existing.id

            new_contract = Contract(
                deal_id=deal_id,
                lead_id=lead_id,
                status=ContractStatus.NEGOTIATING.value,
                contract_terms=sanitize_text(contract_terms, max_len=10000),
                contract_value=contract_value,
                last_updated=datetime.utcnow(),
                review_status=ReviewStatus.PENDING.value,
            )
            session.add(new_contract)
            session.commit()
            session.refresh(new_contract)
            return new_contract.id
        except IntegrityError:
            session.rollback()
            existing = session.query(Contract).filter(Contract.deal_id == deal_id).first()
            if existing:
                return existing.id
            raise
        except SQLAlchemyError:
            session.rollback()
            logger.exception("contract.create.failed", extra={"event": "contract.create.failed", "deal_id": deal_id})
            raise


def fetch_contracts_by_status(status: str) -> List[Contract]:
    with get_db_session() as session:
        try:
            return session.query(Contract).filter(Contract.status == status).all()
        except SQLAlchemyError:
            logger.exception("contract.fetch_by_status.failed", extra={"event": "contract.fetch_by_status.failed", "status": status})
            return []


def update_contract_negotiation(contract_id: int, objections: str, proposed_solutions: str, confidence_score: int) -> None:
    with get_db_session() as session:
        try:
            contract = session.query(Contract).filter(Contract.id == contract_id).first()
            if not contract:
                return
            contract.objections = sanitize_text(objections, max_len=10000)
            contract.proposed_solutions = sanitize_text(proposed_solutions, max_len=10000)
            contract.last_updated = datetime.utcnow()
            # Human review gate is mandatory; never auto-approve.
            contract.review_status = ReviewStatus.PENDING.value
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("contract.negotiation.update_failed", extra={"event": "contract.negotiation.update_failed", "contract_id": contract_id})


def mark_contract_signed(contract_id: int) -> None:
    with get_db_session() as session:
        try:
            contract = session.query(Contract).filter(Contract.id == contract_id).first()
            if not contract:
                return
            contract.status = ContractStatus.SIGNED.value
            contract.signed_date = datetime.utcnow()
            contract.review_status = ReviewStatus.APPROVED.value
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("contract.sign.failed", extra={"event": "contract.sign.failed", "contract_id": contract_id})


def fetch_pending_contract_reviews() -> List[Contract]:
    with get_db_session() as session:
        try:
            return session.query(Contract).filter(Contract.review_status == ReviewStatus.PENDING.value).all()
        except SQLAlchemyError:
            logger.exception("contract.pending_reviews.fetch_failed", extra={"event": "contract.pending_reviews.fetch_failed"})
            return []


def mark_contract_decision(contract_id: int, decision: str, actor: str = "human") -> None:
    with get_db_session() as session:
        try:
            contract = session.query(Contract).filter(Contract.id == contract_id).first()
            if not contract:
                return
            contract.review_status = decision
            if decision == ReviewStatus.APPROVED.value:
                contract.status = ContractStatus.SIGNED.value
                contract.signed_date = datetime.utcnow()
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("contract.review_decision.failed", extra={"event": "contract.review_decision.failed", "contract_id": contract_id})
            return

    _audit_review("contract", contract_id, decision, actor=actor)


# ==============================================================================
# INVOICES - FINANCE AGENT
# ==============================================================================


def create_invoice(contract_id: int, lead_id: int, amount: int, due_date: Union[str, datetime]) -> int:
    with get_db_session() as session:
        try:
            existing = session.query(Invoice).filter(Invoice.contract_id == contract_id).first()
            if existing:
                return existing.id

            due_date_obj = due_date
            if isinstance(due_date, str):
                due_date_obj = datetime.strptime(due_date, "%Y-%m-%d").date()
            elif isinstance(due_date, datetime):
                due_date_obj = due_date.date()

            new_invoice = Invoice(
                contract_id=contract_id,
                lead_id=lead_id,
                amount=amount,
                due_date=due_date_obj,
                status=InvoiceStatus.SENT.value,
                days_overdue=0,
                dunning_stage=0,
                last_contact_date=datetime.utcnow(),
                review_status=ReviewStatus.NEW.value,
            )
            session.add(new_invoice)
            session.commit()
            session.refresh(new_invoice)
            return new_invoice.id
        except IntegrityError:
            session.rollback()
            existing = session.query(Invoice).filter(Invoice.contract_id == contract_id).first()
            if existing:
                return existing.id
            raise
        except SQLAlchemyError:
            session.rollback()
            logger.exception("invoice.create.failed", extra={"event": "invoice.create.failed", "contract_id": contract_id})
            raise


def fetch_invoices_by_status(status: str) -> List[Invoice]:
    with get_db_session() as session:
        try:
            return session.query(Invoice).filter(Invoice.status == status).all()
        except SQLAlchemyError:
            logger.exception("invoice.fetch_by_status.failed", extra={"event": "invoice.fetch_by_status.failed", "status": status})
            return []


def fetch_all_invoices() -> List[Invoice]:
    with get_db_session() as session:
        try:
            return session.query(Invoice).all()
        except SQLAlchemyError:
            logger.exception("invoice.fetch_all.failed", extra={"event": "invoice.fetch_all.failed"})
            return []


def update_invoice_status(invoice_id: int, status: str, days_overdue: int = 0, dunning_stage: int = 0) -> None:
    with get_db_session() as session:
        try:
            invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                return
            invoice.status = status
            invoice.days_overdue = days_overdue
            invoice.dunning_stage = dunning_stage
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("invoice.status.update_failed", extra={"event": "invoice.status.update_failed", "invoice_id": invoice_id})


def save_dunning_draft(invoice_id: int, draft_message: str, confidence_score: int) -> None:
    with get_db_session() as session:
        try:
            invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                return
            invoice.draft_message = sanitize_text(draft_message, max_len=12000)
            invoice.confidence_score = confidence_score
            # Human review gate is mandatory; never auto-approve.
            invoice.review_status = ReviewStatus.PENDING.value
            invoice.last_contact_date = datetime.utcnow()
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("invoice.draft.save_failed", extra={"event": "invoice.draft.save_failed", "invoice_id": invoice_id})


def mark_invoice_paid(invoice_id: int) -> None:
    with get_db_session() as session:
        try:
            invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                return
            invoice.status = InvoiceStatus.PAID.value
            invoice.payment_date = datetime.utcnow()
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("invoice.mark_paid.failed", extra={"event": "invoice.mark_paid.failed", "invoice_id": invoice_id})


def fetch_pending_dunning_reviews() -> List[Invoice]:
    with get_db_session() as session:
        try:
            return session.query(Invoice).filter(Invoice.review_status == ReviewStatus.PENDING.value).all()
        except SQLAlchemyError:
            logger.exception("invoice.pending_reviews.fetch_failed", extra={"event": "invoice.pending_reviews.fetch_failed"})
            return []


def mark_dunning_decision(invoice_id: int, decision: str, actor: str = "human") -> None:
    with get_db_session() as session:
        try:
            invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                return
            invoice.review_status = decision
            if decision == ReviewStatus.APPROVED.value:
                invoice.dunning_stage = (invoice.dunning_stage or 0) + 1
                invoice.last_contact_date = datetime.utcnow()
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("invoice.review_decision.failed", extra={"event": "invoice.review_decision.failed", "invoice_id": invoice_id})
            return

    _audit_review("invoice", invoice_id, decision, actor=actor)


# ==============================================================================
# PHASE 2 SUPPORT HELPERS
# ==============================================================================


def ensure_default_tenant() -> int:
    with get_db_session() as session:
        tenant = session.query(Tenant).filter(Tenant.id == 1).first()
        if tenant:
            return tenant.id
        tenant = Tenant(id=1, name="default")
        session.add(tenant)
        session.commit()
        return tenant.id


def log_llm_interaction(agent_name: str, prompt_text: str, response_text: str, confidence_score: int | None = None, lead_id: int | None = None, tenant_id: int = 1, validation_status: str = "passed") -> None:
    with get_db_session() as session:
        try:
            row = LLMLog(
                tenant_id=tenant_id,
                agent_name=agent_name,
                lead_id=lead_id,
                prompt_text=sanitize_text(prompt_text, max_len=20000),
                response_text=sanitize_text(response_text, max_len=20000),
                confidence_score=confidence_score,
                validation_status=validation_status,
            )
            session.add(row)
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("llm.log.failed", extra={"event": "llm.log.failed", "agent_name": agent_name})


def upsert_prompt_template(agent_name: str, template_key: str, template_body: str) -> int:
    with get_db_session() as session:
        row = session.query(PromptTemplate).filter(PromptTemplate.agent_name == agent_name, PromptTemplate.template_key == template_key).first()
        if not row:
            row = PromptTemplate(agent_name=agent_name, template_key=template_key, template_body=template_body)
            session.add(row)
        else:
            row.template_body = template_body
            row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return row.id


def get_prompt_template(agent_name: str, template_key: str, default: str) -> str:
    with get_db_session() as session:
        row = session.query(PromptTemplate).filter(PromptTemplate.agent_name == agent_name, PromptTemplate.template_key == template_key, PromptTemplate.is_active == True).first()  # noqa: E712
        if row:
            return row.template_body
        return default


def fetch_agent_runs(limit: int = 100) -> list[AgentRun]:
    with get_db_session() as session:
        return session.query(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit).all()


def fetch_email_logs(limit: int = 100) -> list[EmailLog]:
    with get_db_session() as session:
        return session.query(EmailLog).order_by(EmailLog.created_at.desc()).limit(limit).all()
