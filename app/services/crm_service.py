"""
CRM Service - Unified service for CRM dashboard operations.

This service provides:
- Paginated list queries with tenant isolation
- Safe sorting with whitelisted fields
- Search functionality (ILIKE on key fields)
- Mutation methods with audit logging (CRM_MANUAL_OVERRIDE)

NON-NEGOTIABLE RULES:
- All reads are tenant-scoped
- All mutations log to ReviewAudit with CRM_MANUAL_OVERRIDE
- Status enums use Title Case (New, Contacted, Qualified, etc.)
- No raw SQL - SQLAlchemy ORM only
- Review gates preserved via existing mark_review_decision()
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import asc, desc, func, or_
from sqlalchemy.exc import SQLAlchemyError

from app.core.enums import (
    ContractStatus,
    DealStage,
    InvoiceStatus,
    LeadStatus,
    ReviewStatus,
)
from app.database.db import get_db_session
from app.database.models import Contract, Deal, Invoice, Lead, ReviewAudit
from app.services.base_service import BaseService
from app.utils.validators import sanitize_text

logger = logging.getLogger(__name__)


# ==============================================================================
# PAGINATION RESULT
# ==============================================================================


@dataclass
class PaginatedResult:
    """Paginated query result with metadata."""

    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int = field(init=False)

    def __post_init__(self) -> None:
        self.total_pages = math.ceil(self.total / self.page_size) if self.page_size > 0 else 0


# ==============================================================================
# SAFE SORTING WHITELISTS
# ==============================================================================

# Maps sort field names to SQLAlchemy column objects
LEAD_SORT_FIELDS: dict[str, Any] = {
    "created_at": Lead.created_at,
    "status": Lead.status,
    "company": Lead.company,
    "name": Lead.name,
    "signal_score": Lead.signal_score,
    "confidence_score": Lead.confidence_score,
    "review_status": Lead.review_status,
}

DEAL_SORT_FIELDS: dict[str, Any] = {
    "created_at": Deal.created_at,
    "stage": Deal.stage,
    "company": Deal.company,
    "deal_value": Deal.deal_value,
    "probability": Deal.probability,
    "expected_close_date": Deal.expected_close_date,
    "review_status": Deal.review_status,
}

CONTRACT_SORT_FIELDS: dict[str, Any] = {
    "last_updated": Contract.last_updated,
    "status": Contract.status,
    "contract_value": Contract.contract_value,
    "review_status": Contract.review_status,
}

INVOICE_SORT_FIELDS: dict[str, Any] = {
    "due_date": Invoice.due_date,
    "status": Invoice.status,
    "amount": Invoice.amount,
    "dunning_stage": Invoice.dunning_stage,
    "review_status": Invoice.review_status,
}

# Valid status values for filtering (Title Case)
LEAD_STATUS_VALUES = [e.value for e in LeadStatus]
DEAL_STAGE_VALUES = [e.value for e in DealStage]
CONTRACT_STATUS_VALUES = [e.value for e in ContractStatus]
INVOICE_STATUS_VALUES = [e.value for e in InvoiceStatus]


# ==============================================================================
# EXCEPTIONS
# ==============================================================================


class InvalidSortFieldError(ValueError):
    """Raised when an invalid sort field is provided."""

    def __init__(self, field: str, valid_fields: list[str]) -> None:
        super().__init__(f"Invalid sort field '{field}'. Valid fields: {', '.join(valid_fields)}")
        self.field = field
        self.valid_fields = valid_fields


class InvalidStatusError(ValueError):
    """Raised when an invalid status value is provided."""

    def __init__(self, status: str, valid_statuses: list[str]) -> None:
        super().__init__(f"Invalid status '{status}'. Valid values: {', '.join(valid_statuses)}")
        self.status = status
        self.valid_statuses = valid_statuses


class TenantOwnershipError(Exception):
    """Raised when an entity does not belong to the specified tenant."""

    def __init__(self, entity_type: str, entity_id: int, tenant_id: int) -> None:
        super().__init__(f"{entity_type} {entity_id} does not belong to tenant {tenant_id}")
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.tenant_id = tenant_id


class InvalidStageTransitionError(Exception):
    """Raised when an invalid stage transition is attempted."""

    def __init__(self, current_stage: str, new_stage: str) -> None:
        super().__init__(f"Cannot transition from '{current_stage}' to '{new_stage}'")
        self.current_stage = current_stage
        self.new_stage = new_stage


# ==============================================================================
# AUDIT LOGGING
# ==============================================================================


def _log_crm_mutation(
    entity_type: str,
    entity_id: int,
    decision: str,
    notes: str = "",
    actor: str = "CRM_MANUAL_OVERRIDE",
) -> None:
    """Log a CRM mutation to the ReviewAudit table."""
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
            logger.info(
                "crm.mutation.audited",
                extra={
                    "event": "crm.mutation.audited",
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "decision": decision,
                    "actor": actor,
                },
            )
    except SQLAlchemyError:
        logger.exception(
            "crm.mutation.audit_failed",
            extra={"event": "crm.mutation.audit_failed", "entity_type": entity_type, "entity_id": entity_id},
        )


# ==============================================================================
# CRM SERVICE CLASS
# ==============================================================================


class CRMService(BaseService):
    """
    Unified CRM service for dashboard operations.

    Extends BaseService for context manager support and transaction handling.
    """

    # ==========================================================================
    # LEAD METHODS
    # ==========================================================================

    def get_leads(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        search: str | None = None,
        status: str | None = None,
        review_status: str | None = None,
    ) -> PaginatedResult:
        """
        Get paginated leads for a tenant.

        Args:
            tenant_id: Tenant ID for isolation
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            sort_by: Sort field (must be in LEAD_SORT_FIELDS)
            sort_order: 'asc' or 'desc'
            search: Optional search string (ILIKE on name, email, company)
            status: Optional status filter (must be valid LeadStatus)
            review_status: Optional review status filter

        Returns:
            PaginatedResult with leads and metadata

        Raises:
            InvalidSortFieldError: If sort_by is not in whitelist
            InvalidStatusError: If status is not a valid LeadStatus
        """
        # Validate sort field
        if sort_by not in LEAD_SORT_FIELDS:
            raise InvalidSortFieldError(sort_by, list(LEAD_SORT_FIELDS.keys()))

        # Validate status
        if status is not None and status not in LEAD_STATUS_VALUES:
            raise InvalidStatusError(status, LEAD_STATUS_VALUES)

        # Clamp page_size
        page_size = min(max(page_size, 1), 100)
        page = max(page, 1)

        with get_db_session() as session:
            query = session.query(Lead).filter(Lead.tenant_id == tenant_id)

            # Apply status filter
            if status is not None:
                query = query.filter(Lead.status == status)

            # Apply review_status filter
            if review_status is not None:
                query = query.filter(Lead.review_status == review_status)

            # Apply search (ILIKE on name, email, company)
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        Lead.name.ilike(search_pattern),
                        Lead.email.ilike(search_pattern),
                        Lead.company.ilike(search_pattern),
                    )
                )

            # Get total count
            total = query.count()

            # Apply sorting
            sort_column = LEAD_SORT_FIELDS[sort_by]
            if sort_order.lower() == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))

            # Apply pagination
            offset = (page - 1) * page_size
            leads = query.offset(offset).limit(page_size).all()

            # Convert to dicts
            items = [
                {
                    "id": lead.id,
                    "name": lead.name,
                    "email": lead.email,
                    "company": lead.company,
                    "role": lead.role,
                    "industry": lead.industry,
                    "website": lead.website,
                    "location": lead.location,
                    "company_size": lead.company_size,
                    "status": lead.status,
                    "review_status": lead.review_status,
                    "signal_score": lead.signal_score,
                    "confidence_score": lead.confidence_score,
                    "draft_message": lead.draft_message,
                    "last_contacted": lead.last_contacted.isoformat() if lead.last_contacted else None,
                    "created_at": lead.created_at.isoformat() if lead.created_at else None,
                }
                for lead in leads
            ]

            return PaginatedResult(items=items, total=total, page=page, page_size=page_size)

    def approve_lead_draft_safe(
        self,
        tenant_id: int,
        lead_id: int,
        edited_email: str | None = None,
        actor: str = "CRM_MANUAL_OVERRIDE",
    ) -> Lead | None:
        """
        Approve a lead draft - uses existing mark_review_decision pattern.

        This method:
        1. Validates tenant ownership
        2. Updates the lead to Contacted status
        3. Logs to ReviewAudit

        Args:
            tenant_id: Tenant ID for isolation
            lead_id: Lead ID to approve
            edited_email: Optional edited email content
            actor: Actor for audit log

        Returns:
            Updated Lead or None if not found

        Raises:
            TenantOwnershipError: If lead does not belong to tenant
        """
        with get_db_session() as session:
            lead = session.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return None

            # Validate tenant ownership
            if lead.tenant_id != tenant_id:
                raise TenantOwnershipError("Lead", lead_id, tenant_id)

            # Update lead
            lead.status = LeadStatus.CONTACTED.value
            lead.review_status = ReviewStatus.APPROVED.value
            if edited_email:
                lead.draft_message = sanitize_text(edited_email, max_len=12000)
            lead.last_contacted = datetime.utcnow()

            session.commit()
            session.refresh(lead)

            # Log audit
            _log_crm_mutation(
                entity_type="lead",
                entity_id=lead_id,
                decision="Approved",
                notes=f"Email approved via CRM. Status changed to {LeadStatus.CONTACTED.value}",
                actor=actor,
            )

            logger.info(
                "crm.lead.approved",
                extra={"event": "crm.lead.approved", "lead_id": lead_id, "tenant_id": tenant_id, "actor": actor},
            )

            return lead

    def reject_lead_draft_safe(
        self,
        tenant_id: int,
        lead_id: int,
        reason: str = "",
        actor: str = "CRM_MANUAL_OVERRIDE",
    ) -> Lead | None:
        """
        Reject a lead draft.

        Args:
            tenant_id: Tenant ID for isolation
            lead_id: Lead ID to reject
            reason: Rejection reason
            actor: Actor for audit log

        Returns:
            Updated Lead or None if not found

        Raises:
            TenantOwnershipError: If lead does not belong to tenant
        """
        with get_db_session() as session:
            lead = session.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return None

            # Validate tenant ownership
            if lead.tenant_id != tenant_id:
                raise TenantOwnershipError("Lead", lead_id, tenant_id)

            # Update lead
            lead.review_status = ReviewStatus.REJECTED.value

            session.commit()
            session.refresh(lead)

            # Log audit
            _log_crm_mutation(
                entity_type="lead",
                entity_id=lead_id,
                decision="Rejected",
                notes=f"Rejected via CRM. Reason: {reason}",
                actor=actor,
            )

            logger.info(
                "crm.lead.rejected",
                extra={"event": "crm.lead.rejected", "lead_id": lead_id, "tenant_id": tenant_id, "actor": actor},
            )

            return lead

    # ==========================================================================
    # DEAL METHODS
    # ==========================================================================

    def get_deals(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        search: str | None = None,
        stage: str | None = None,
        review_status: str | None = None,
    ) -> PaginatedResult:
        """
        Get paginated deals for a tenant.

        Args:
            tenant_id: Tenant ID for isolation
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            sort_by: Sort field (must be in DEAL_SORT_FIELDS)
            sort_order: 'asc' or 'desc'
            search: Optional search string (ILIKE on company)
            stage: Optional stage filter (must be valid DealStage)
            review_status: Optional review status filter

        Returns:
            PaginatedResult with deals and metadata

        Raises:
            InvalidSortFieldError: If sort_by is not in whitelist
            InvalidStatusError: If stage is not a valid DealStage
        """
        # Validate sort field
        if sort_by not in DEAL_SORT_FIELDS:
            raise InvalidSortFieldError(sort_by, list(DEAL_SORT_FIELDS.keys()))

        # Validate stage
        if stage is not None and stage not in DEAL_STAGE_VALUES:
            raise InvalidStatusError(stage, DEAL_STAGE_VALUES)

        # Clamp page_size
        page_size = min(max(page_size, 1), 100)
        page = max(page, 1)

        with get_db_session() as session:
            query = session.query(Deal).filter(Deal.tenant_id == tenant_id)

            # Apply stage filter
            if stage is not None:
                query = query.filter(Deal.stage == stage)

            # Apply review_status filter
            if review_status is not None:
                query = query.filter(Deal.review_status == review_status)

            # Apply search (ILIKE on company)
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(Deal.company.ilike(search_pattern))

            # Get total count
            total = query.count()

            # Apply sorting
            sort_column = DEAL_SORT_FIELDS[sort_by]
            if sort_order.lower() == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))

            # Apply pagination
            offset = (page - 1) * page_size
            deals = query.offset(offset).limit(page_size).all()

            # Convert to dicts
            items = [
                {
                    "id": deal.id,
                    "lead_id": deal.lead_id,
                    "company": deal.company,
                    "acv": deal.acv,
                    "deal_value": deal.deal_value,
                    "stage": deal.stage,
                    "status": deal.status,
                    "probability": deal.probability,
                    "probability_confidence": deal.probability_confidence,
                    "expected_close_date": deal.expected_close_date.isoformat() if deal.expected_close_date else None,
                    "margin": deal.margin,
                    "segment_tag": deal.segment_tag,
                    "review_status": deal.review_status,
                    "notes": deal.notes,
                    "created_at": deal.created_at.isoformat() if deal.created_at else None,
                    "last_updated": deal.last_updated.isoformat() if deal.last_updated else None,
                }
                for deal in deals
            ]

            return PaginatedResult(items=items, total=total, page=page, page_size=page_size)

    def override_deal_stage_safe(
        self,
        tenant_id: int,
        deal_id: int,
        new_stage: str,
        reason: str = "",
        actor: str = "CRM_MANUAL_OVERRIDE",
    ) -> Deal | None:
        """
        Override deal stage with validation.

        Args:
            tenant_id: Tenant ID for isolation
            deal_id: Deal ID to update
            new_stage: New stage value (must be valid DealStage)
            reason: Reason for override
            actor: Actor for audit log

        Returns:
            Updated Deal or None if not found

        Raises:
            TenantOwnershipError: If deal does not belong to tenant
            InvalidStatusError: If new_stage is not a valid DealStage
        """
        # Validate new stage
        if new_stage not in DEAL_STAGE_VALUES:
            raise InvalidStatusError(new_stage, DEAL_STAGE_VALUES)

        with get_db_session() as session:
            deal = session.query(Deal).filter(Deal.id == deal_id).first()
            if not deal:
                return None

            # Validate tenant ownership
            if deal.tenant_id != tenant_id:
                raise TenantOwnershipError("Deal", deal_id, tenant_id)

            old_stage = deal.stage
            deal.stage = new_stage
            deal.last_updated = datetime.utcnow()
            if reason:
                deal.notes = (deal.notes or "") + f"\n[Stage Override] {reason}"

            session.commit()
            session.refresh(deal)

            # Log audit
            _log_crm_mutation(
                entity_type="deal",
                entity_id=deal_id,
                decision="Stage Override",
                notes=f"Stage changed from '{old_stage}' to '{new_stage}'. Reason: {reason}",
                actor=actor,
            )

            logger.info(
                "crm.deal.stage_override",
                extra={
                    "event": "crm.deal.stage_override",
                    "deal_id": deal_id,
                    "tenant_id": tenant_id,
                    "old_stage": old_stage,
                    "new_stage": new_stage,
                    "actor": actor,
                },
            )

            return deal

    # ==========================================================================
    # CONTRACT METHODS
    # ==========================================================================

    def get_contracts(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "last_updated",
        sort_order: str = "desc",
        search: str | None = None,
        status: str | None = None,
        review_status: str | None = None,
    ) -> PaginatedResult:
        """
        Get paginated contracts for a tenant.

        Args:
            tenant_id: Tenant ID for isolation
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            sort_by: Sort field (must be in CONTRACT_SORT_FIELDS)
            sort_order: 'asc' or 'desc'
            search: Optional search (not implemented for contracts)
            status: Optional status filter (must be valid ContractStatus)
            review_status: Optional review status filter

        Returns:
            PaginatedResult with contracts and metadata

        Raises:
            InvalidSortFieldError: If sort_by is not in whitelist
            InvalidStatusError: If status is not a valid ContractStatus
        """
        # Validate sort field
        if sort_by not in CONTRACT_SORT_FIELDS:
            raise InvalidSortFieldError(sort_by, list(CONTRACT_SORT_FIELDS.keys()))

        # Validate status
        if status is not None and status not in CONTRACT_STATUS_VALUES:
            raise InvalidStatusError(status, CONTRACT_STATUS_VALUES)

        # Clamp page_size
        page_size = min(max(page_size, 1), 100)
        page = max(page, 1)

        with get_db_session() as session:
            query = session.query(Contract).filter(Contract.tenant_id == tenant_id)

            # Apply status filter
            if status is not None:
                query = query.filter(Contract.status == status)

            # Apply review_status filter
            if review_status is not None:
                query = query.filter(Contract.review_status == review_status)

            # Get total count
            total = query.count()

            # Apply sorting
            sort_column = CONTRACT_SORT_FIELDS[sort_by]
            if sort_order.lower() == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))

            # Apply pagination
            offset = (page - 1) * page_size
            contracts = query.offset(offset).limit(page_size).all()

            # Convert to dicts
            items = [
                {
                    "id": contract.id,
                    "contract_code": contract.contract_code,
                    "deal_id": contract.deal_id,
                    "lead_id": contract.lead_id,
                    "status": contract.status,
                    "contract_terms": contract.contract_terms,
                    "contract_value": contract.contract_value,
                    "negotiation_points": contract.negotiation_points,
                    "objections": contract.objections,
                    "proposed_solutions": contract.proposed_solutions,
                    "negotiation_turn": contract.negotiation_turn,
                    "confidence_score": contract.confidence_score,
                    "signed_date": contract.signed_date.isoformat() if contract.signed_date else None,
                    "review_status": contract.review_status,
                    "last_updated": contract.last_updated.isoformat() if contract.last_updated else None,
                }
                for contract in contracts
            ]

            return PaginatedResult(items=items, total=total, page=page, page_size=page_size)

    def sign_contract_safe(
        self,
        tenant_id: int,
        contract_id: int,
        actor: str = "CRM_MANUAL_OVERRIDE",
    ) -> Contract | None:
        """
        Mark a contract as signed.

        Args:
            tenant_id: Tenant ID for isolation
            contract_id: Contract ID to sign
            actor: Actor for audit log

        Returns:
            Updated Contract or None if not found

        Raises:
            TenantOwnershipError: If contract does not belong to tenant
        """
        with get_db_session() as session:
            contract = session.query(Contract).filter(Contract.id == contract_id).first()
            if not contract:
                return None

            # Validate tenant ownership
            if contract.tenant_id != tenant_id:
                raise TenantOwnershipError("Contract", contract_id, tenant_id)

            old_status = contract.status
            contract.status = ContractStatus.SIGNED.value
            contract.signed_date = datetime.utcnow()
            contract.last_updated = datetime.utcnow()

            session.commit()
            session.refresh(contract)

            # Log audit
            _log_crm_mutation(
                entity_type="contract",
                entity_id=contract_id,
                decision="Signed",
                notes=f"Contract signed. Previous status: {old_status}",
                actor=actor,
            )

            logger.info(
                "crm.contract.signed",
                extra={
                    "event": "crm.contract.signed",
                    "contract_id": contract_id,
                    "tenant_id": tenant_id,
                    "actor": actor,
                },
            )

            return contract

    # ==========================================================================
    # INVOICE METHODS
    # ==========================================================================

    def get_invoices(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "due_date",
        sort_order: str = "desc",
        search: str | None = None,
        status: str | None = None,
        review_status: str | None = None,
    ) -> PaginatedResult:
        """
        Get paginated invoices for a tenant.

        Args:
            tenant_id: Tenant ID for isolation
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            sort_by: Sort field (must be in INVOICE_SORT_FIELDS)
            sort_order: 'asc' or 'desc'
            search: Optional search (not implemented for invoices)
            status: Optional status filter (must be valid InvoiceStatus)
            review_status: Optional review status filter

        Returns:
            PaginatedResult with invoices and metadata

        Raises:
            InvalidSortFieldError: If sort_by is not in whitelist
            InvalidStatusError: If status is not a valid InvoiceStatus
        """
        # Validate sort field
        if sort_by not in INVOICE_SORT_FIELDS:
            raise InvalidSortFieldError(sort_by, list(INVOICE_SORT_FIELDS.keys()))

        # Validate status
        if status is not None and status not in INVOICE_STATUS_VALUES:
            raise InvalidStatusError(status, INVOICE_STATUS_VALUES)

        # Clamp page_size
        page_size = min(max(page_size, 1), 100)
        page = max(page, 1)

        with get_db_session() as session:
            # Invoice doesn't have tenant_id, join with Contract for tenant filtering
            query = session.query(Invoice).join(
                Contract, Invoice.contract_id == Contract.id
            ).filter(Contract.tenant_id == tenant_id)

            # Apply status filter
            if status is not None:
                query = query.filter(Invoice.status == status)

            # Apply review_status filter
            if review_status is not None:
                query = query.filter(Invoice.review_status == review_status)

            # Get total count
            total = query.count()

            # Apply sorting
            sort_column = INVOICE_SORT_FIELDS[sort_by]
            if sort_order.lower() == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))

            # Apply pagination
            offset = (page - 1) * page_size
            invoices = query.offset(offset).limit(page_size).all()

            # Convert to dicts
            items = [
                {
                    "id": invoice.id,
                    "invoice_code": invoice.invoice_code,
                    "contract_id": invoice.contract_id,
                    "lead_id": invoice.lead_id,
                    "amount": invoice.amount,
                    "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                    "status": invoice.status,
                    "days_overdue": invoice.days_overdue,
                    "dunning_stage": invoice.dunning_stage,
                    "last_contact_date": invoice.last_contact_date.isoformat() if invoice.last_contact_date else None,
                    "payment_date": invoice.payment_date.isoformat() if invoice.payment_date else None,
                    "draft_message": invoice.draft_message,
                    "confidence_score": invoice.confidence_score,
                    "review_status": invoice.review_status,
                    "tenant_id": invoice.contract.tenant_id if invoice.contract else tenant_id,
                }
                for invoice in invoices
            ]

            return PaginatedResult(items=items, total=total, page=page, page_size=page_size)

    def mark_invoice_paid_safe(
        self,
        tenant_id: int,
        invoice_id: int,
        actor: str = "CRM_MANUAL_OVERRIDE",
    ) -> Invoice | None:
        """
        Mark an invoice as paid.

        Args:
            tenant_id: Tenant ID for isolation
            invoice_id: Invoice ID to mark as paid
            actor: Actor for audit log

        Returns:
            Updated Invoice or None if not found

        Raises:
            TenantOwnershipError: If invoice does not belong to tenant
        """
        with get_db_session() as session:
            # Join with Contract to validate tenant ownership
            invoice = (
                session.query(Invoice)
                .join(Contract, Invoice.contract_id == Contract.id)
                .filter(Invoice.id == invoice_id)
                .filter(Contract.tenant_id == tenant_id)
                .first()
            )
            if not invoice:
                return None

            old_status = invoice.status
            invoice.status = InvoiceStatus.PAID.value
            invoice.payment_date = datetime.utcnow()

            session.commit()
            session.refresh(invoice)

            # Log audit
            _log_crm_mutation(
                entity_type="invoice",
                entity_id=invoice_id,
                decision="Paid",
                notes=f"Invoice marked as paid. Previous status: {old_status}",
                actor=actor,
            )

            logger.info(
                "crm.invoice.paid",
                extra={
                    "event": "crm.invoice.paid",
                    "invoice_id": invoice_id,
                    "tenant_id": tenant_id,
                    "actor": actor,
                },
            )

            return invoice


# ==============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# ==============================================================================

_service = CRMService()


def get_leads(*args, **kwargs) -> PaginatedResult:
    """Convenience function for CRMService.get_leads."""
    return _service.get_leads(*args, **kwargs)


def get_deals(*args, **kwargs) -> PaginatedResult:
    """Convenience function for CRMService.get_deals."""
    return _service.get_deals(*args, **kwargs)


def get_contracts(*args, **kwargs) -> PaginatedResult:
    """Convenience function for CRMService.get_contracts."""
    return _service.get_contracts(*args, **kwargs)


def get_invoices(*args, **kwargs) -> PaginatedResult:
    """Convenience function for CRMService.get_invoices."""
    return _service.get_invoices(*args, **kwargs)
