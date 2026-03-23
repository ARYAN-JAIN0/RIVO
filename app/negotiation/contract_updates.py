"""Contract update layer for negotiation adjustments.

This module handles:
- Price adjustments within allowed bounds
- Timeline updates
- Validation against deal constraints
- Before/after value logging

This is a deterministic system component (no LLM involved).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.database.db import get_db_session
from app.database.models import Contract, Deal

logger = logging.getLogger(__name__)

# Pricing constraints
MAX_DISCOUNT_PERCENT = 20  # Maximum discount allowed without approval
MIN_DEAL_VALUE = 1000  # Minimum deal value


@dataclass
class ContractUpdateResult:
    """Result of contract update operation."""
    success: bool
    price_changed: bool
    timeline_changed: bool
    previous_value: int | None
    new_value: int | None
    previous_date: datetime | None
    new_date: datetime | None
    validation_errors: list[str]
    log_message: str


def _validate_price_change(
    current_value: int,
    new_value: int,
    max_discount_percent: int = MAX_DISCOUNT_PERCENT,
) -> tuple[bool, str]:
    """Validate price change is within allowed bounds.
    
    Args:
        current_value: Current contract value.
        new_value: Proposed new value.
        max_discount_percent: Maximum discount allowed.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    if new_value < MIN_DEAL_VALUE:
        return False, f"Deal value must be at least ${MIN_DEAL_VALUE:,}"
    
    if new_value > current_value:
        # Price increase is always allowed
        return True, ""
    
    # Calculate discount percentage
    discount_percent = ((current_value - new_value) / current_value) * 100
    
    if discount_percent > max_discount_percent:
        return False, f"Discount exceeds maximum of {max_discount_percent}%"
    
    return True, ""


def _validate_timeline_change(
    current_date: datetime | None,
    new_date: datetime,
) -> tuple[bool, str]:
    """Validate timeline change is reasonable.
    
    Args:
        current_date: Current expected close date.
        new_date: Proposed new date.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    if new_date < datetime.utcnow():
        return False, "Timeline cannot be in the past"
    
    # Allow deferral up to 6 months
    if current_date:
        max_deferral = timedelta(days=180)
        if new_date - current_date > max_deferral:
            return False, "Timeline deferral cannot exceed 6 months"
    
    return True, ""


def update_price(
    contract_id: int,
    new_value: int,
    tenant_id: int = 1,
    reason: str = "",
) -> ContractUpdateResult:
    """Update contract price within allowed bounds.
    
    Args:
        contract_id: The contract ID to update.
        new_value: The new deal value.
        tenant_id: The tenant ID for isolation.
        reason: Optional reason for the change.
        
    Returns:
        ContractUpdateResult with update status and before/after values.
    """
    with get_db_session() as session:
        contract = (
            session.query(Contract)
            .filter(Contract.id == contract_id, Contract.tenant_id == tenant_id)
            .first()
        )
        
        if not contract:
            logger.warning(
                "negotiation.contract_update.contract_not_found",
                extra={
                    "event": "negotiation.contract_update.contract_not_found",
                    "contract_id": contract_id,
                    "tenant_id": tenant_id,
                },
            )
            return ContractUpdateResult(
                success=False,
                price_changed=False,
                timeline_changed=False,
                previous_value=None,
                new_value=None,
                previous_date=None,
                new_date=None,
                validation_errors=["Contract not found"],
                log_message="Contract not found",
            )
        
        # Get current values
        previous_value = contract.contract_value or 0
        previous_date = contract.deal.expected_close_date if contract.deal else None
        
        # Validate price change
        is_valid, error = _validate_price_change(previous_value, new_value)
        
        if not is_valid:
            logger.warning(
                "negotiation.contract_update.price_invalid",
                extra={
                    "event": "negotiation.contract_update.price_invalid",
                    "contract_id": contract_id,
                    "previous_value": previous_value,
                    "new_value": new_value,
                    "error": error,
                },
            )
            return ContractUpdateResult(
                success=False,
                price_changed=False,
                timeline_changed=False,
                previous_value=previous_value,
                new_value=new_value,
                previous_date=previous_date,
                new_date=None,
                validation_errors=[error],
                log_message=f"Price change rejected: {error}",
            )
        
        # Apply the update
        contract.contract_value = new_value
        contract.last_updated = datetime.utcnow()
        
        # Log the change in notes
        discount = ((previous_value - new_value) / previous_value * 100) if previous_value > 0 else 0
        note = f"\n[{datetime.utcnow().isoformat()}] Price adjustment: ${previous_value:,} -> ${new_value:,} ({discount:.1f}% discount). Reason: {reason}"
        contract.notes = (contract.notes or "") + note
        
        session.commit()
        
        logger.info(
            "negotiation.contract_update.price_updated",
            extra={
                "event": "negotiation.contract_update.price_updated",
                "contract_id": contract_id,
                "previous_value": previous_value,
                "new_value": new_value,
                "discount_percent": discount,
                "reason": reason,
            },
        )
        
        return ContractUpdateResult(
            success=True,
            price_changed=True,
            timeline_changed=False,
            previous_value=previous_value,
            new_value=new_value,
            previous_date=previous_date,
            new_date=None,
            validation_errors=[],
            log_message=f"Price updated: ${previous_value:,} -> ${new_value:,}",
        )


def update_timeline(
    contract_id: int,
    new_close_date: datetime,
    tenant_id: int = 1,
    reason: str = "",
) -> ContractUpdateResult:
    """Update contract timeline.
    
    Args:
        contract_id: The contract ID to update.
        new_close_date: The new expected close date.
        tenant_id: The tenant ID for isolation.
        reason: Optional reason for the change.
        
    Returns:
        ContractUpdateResult with update status and before/after dates.
    """
    with get_db_session() as session:
        contract = (
            session.query(Contract)
            .filter(Contract.id == contract_id, Contract.tenant_id == tenant_id)
            .first()
        )
        
        if not contract or not contract.deal:
            logger.warning(
                "negotiation.contract_update.contract_not_found",
                extra={
                    "event": "negotiation.contract_update.contract_not_found",
                    "contract_id": contract_id,
                    "tenant_id": tenant_id,
                },
            )
            return ContractUpdateResult(
                success=False,
                price_changed=False,
                timeline_changed=False,
                previous_value=None,
                new_value=None,
                previous_date=None,
                new_date=None,
                validation_errors=["Contract or deal not found"],
                log_message="Contract or deal not found",
            )
        
        # Get current values
        previous_value = contract.contract_value or 0
        previous_date = contract.deal.expected_close_date
        
        # Validate timeline change
        is_valid, error = _validate_timeline_change(previous_date, new_close_date)
        
        if not is_valid:
            logger.warning(
                "negotiation.contract_update.timeline_invalid",
                extra={
                    "event": "negotiation.contract_update.timeline_invalid",
                    "contract_id": contract_id,
                    "previous_date": previous_date.isoformat() if previous_date else None,
                    "new_date": new_close_date.isoformat(),
                    "error": error,
                },
            )
            return ContractUpdateResult(
                success=False,
                price_changed=False,
                timeline_changed=False,
                previous_value=previous_value,
                new_value=None,
                previous_date=previous_date,
                new_date=new_close_date,
                validation_errors=[error],
                log_message=f"Timeline change rejected: {error}",
            )
        
        # Apply the update
        from datetime import date
        contract.deal.expected_close_date = date(new_close_date.year, new_close_date.month, new_close_date.day)
        contract.last_updated = datetime.utcnow()
        
        # Log the change in notes
        note = f"\n[{datetime.utcnow().isoformat()}] Timeline adjusted: {previous_date.isoformat() if previous_date else 'N/A'} -> {new_close_date.date().isoformat()}. Reason: {reason}"
        contract.notes = (contract.notes or "") + note
        
        session.commit()
        
        logger.info(
            "negotiation.contract_update.timeline_updated",
            extra={
                "event": "negotiation.contract_update.timeline_updated",
                "contract_id": contract_id,
                "previous_date": previous_date.isoformat() if previous_date else None,
                "new_date": new_close_date.date().isoformat(),
                "reason": reason,
            },
        )
        
        return ContractUpdateResult(
            success=True,
            price_changed=False,
            timeline_changed=True,
            previous_value=previous_value,
            new_value=None,
            previous_date=previous_date,
            new_date=new_close_date,
            validation_errors=[],
            log_message=f"Timeline updated: {previous_date.date().isoformat() if previous_date else 'N/A'} -> {new_close_date.date().isoformat()}",
        )


def get_contract_constraints(
    contract_id: int,
    tenant_id: int = 1,
) -> dict | None:
    """Get contract constraints for validation.
    
    Args:
        contract_id: The contract ID.
        tenant_id: The tenant ID for isolation.
        
    Returns:
        Dict with constraints or None if not found.
    """
    with get_db_session() as session:
        contract = (
            session.query(Contract)
            .filter(Contract.id == contract_id, Contract.tenant_id == tenant_id)
            .first()
        )
        
        if not contract:
            return None
        
        return {
            "contract_id": contract.id,
            "current_value": contract.contract_value or 0,
            "min_value": MIN_DEAL_VALUE,
            "max_discount_percent": MAX_DISCOUNT_PERCENT,
            "current_close_date": contract.deal.expected_close_date.isoformat() if contract.deal and contract.deal.expected_close_date else None,
            "negotiation_turn": contract.negotiation_turn or 0,
        }
