"""Finance scoring module for payment risk assessment.

This module provides customer risk scoring functionality based on payment history
and invoice data, with full tenant isolation support.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.db import get_db_session
from app.database.models import Invoice, Lead


# Default fallback values for error cases
DEFAULT_FALLBACK = {
    "risk_score": 0.5,
    "on_time_ratio": 0.5,
    "avg_delay_days": 0,
    "max_delay_days": 0,
    "total_payments": 0,
    "on_time_payments": 0,
}


def _min_max_normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize a value using min-max scaling, bounded between 0 and 1.

    Args:
        value: The value to normalize.
        min_val: Minimum value in the range.
        max_val: Maximum value in the range.

    Returns:
        Normalized value between 0 and 1.
    """
    if max_val <= min_val:
        return 0.0
    normalized = (value - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))


def calculate_customer_risk_score(tenant_id: int, customer_id: int) -> dict[str, Any]:
    """Calculate payment risk score for a customer.

    Computes risk score based on:
    - on_time_ratio: percentage of payments made on or before due date
    - avg_delay_days: average delay for late payments
    - max_delay_days: maximum delay for late payments
    - deal_size_normalized: customer's invoice total relative to tenant total

    Risk score formula:
    risk_score = (0.4 * (1 - on_time_ratio))
               + (0.3 * normalized_avg_delay)
               + (0.2 * normalized_max_delay)
               + (0.1 * deal_size_normalized)

    Args:
        tenant_id: The tenant ID for multi-tenant isolation.
        customer_id: The customer (lead) ID to calculate risk for.

    Returns:
        Dictionary containing risk score and related metrics:
        - risk_score: float (0-1, higher = more risky)
        - on_time_ratio: float (0-1)
        - avg_delay_days: float
        - max_delay_days: float
        - total_payments: int
        - on_time_payments: int
    """
    try:
        with get_db_session() as session:
            return _calculate_risk_score_impl(session, tenant_id, customer_id)
    except Exception:
        # Fallback on any error - return safe default
        return DEFAULT_FALLBACK.copy()


def _calculate_risk_score_impl(session: Session, tenant_id: int, customer_id: int) -> dict[str, Any]:
    """Internal implementation of risk score calculation.

    Args:
        session: Database session.
        tenant_id: Tenant ID for filtering.
        customer_id: Customer (lead) ID.

    Returns:
        Risk score dictionary.
    """
    # Get all paid invoices for this customer (lead_id = customer_id)
    # payment_date indicates when payment was made
    invoices = (
        session.query(Invoice)
        .filter(
            Invoice.tenant_id == tenant_id,
            Invoice.lead_id == customer_id,
            Invoice.payment_date.isnot(None),
            Invoice.due_date.isnot(None),
        )
        .all()
    )

    total_payments = len(invoices)

    # Edge case: no payment history
    if total_payments == 0:
        return DEFAULT_FALLBACK.copy()

    # Calculate on-time payments and delays
    on_time_count = 0
    delay_days = []

    for inv in invoices:
        payment_date = inv.payment_date
        due_date = inv.due_date

        # Handle both datetime and date types
        if hasattr(payment_date, 'date'):
            payment_date = payment_date.date()
        if hasattr(due_date, 'date'):
            due_date = due_date.date()

        if payment_date <= due_date:
            on_time_count += 1
        else:
            delay = (payment_date - due_date).days
            delay_days.append(delay)

    # Calculate metrics
    on_time_ratio = on_time_count / total_payments if total_payments > 0 else 0.5

    avg_delay_days = sum(delay_days) / len(delay_days) if delay_days else 0
    max_delay_days = max(delay_days) if delay_days else 0

    # Get tenant-level delay statistics for normalization
    tenant_delays = _get_tenant_delay_stats(session, tenant_id)

    # Normalize delays using tenant statistics
    normalized_avg_delay = _min_max_normalize(
        avg_delay_days,
        tenant_delays["min_delay"],
        tenant_delays["max_delay"]
    )
    normalized_max_delay = _min_max_normalize(
        max_delay_days,
        tenant_delays["min_delay"],
        tenant_delays["max_delay"]
    )

    # Calculate deal size normalized
    deal_size_normalized = _calculate_deal_size_normalized(session, tenant_id, customer_id)

    # Compute final risk score
    risk_score = (
        (0.4 * (1 - on_time_ratio))
        + (0.3 * normalized_avg_delay)
        + (0.2 * normalized_max_delay)
        + (0.1 * deal_size_normalized)
    )

    # Ensure risk_score is bounded between 0 and 1
    risk_score = max(0.0, min(1.0, risk_score))

    return {
        "risk_score": round(risk_score, 4),
        "on_time_ratio": round(on_time_ratio, 4),
        "avg_delay_days": round(avg_delay_days, 2),
        "max_delay_days": max_delay_days,
        "total_payments": total_payments,
        "on_time_payments": on_time_count,
    }


def _get_tenant_delay_stats(session: Session, tenant_id: int) -> dict[str, float]:
    """Get tenant-level delay statistics for normalization.

    Args:
        session: Database session.
        tenant_id: Tenant ID.

    Returns:
        Dictionary with min_delay and max_delay values.
    """
    # Get all late payments for the tenant
    late_payments = (
        session.query(
            func.julianday(Invoice.payment_date) - func.julianday(Invoice.due_date)
        )
        .filter(
            Invoice.tenant_id == tenant_id,
            Invoice.payment_date.isnot(None),
            Invoice.due_date.isnot(None),
            Invoice.payment_date > Invoice.due_date,
        )
        .all()
    )

    if not late_payments:
        # Return default range if no late payments found
        return {"min_delay": 0.0, "max_delay": 30.0}

    delays = [float(delay[0]) for delay in late_payments if delay[0] is not None]
    if not delays:
        return {"min_delay": 0.0, "max_delay": 30.0}

    return {
        "min_delay": min(delays),
        "max_delay": max(delays),
    }


def _calculate_deal_size_normalized(
    session: Session, tenant_id: int, customer_id: int
) -> float:
    """Calculate normalized deal size for customer relative to tenant.

    Args:
        session: Database session.
        tenant_id: Tenant ID.
        customer_id: Customer (lead) ID.

    Returns:
        Normalized deal size (0-1).
    """
    # Get customer's total invoice amount
    customer_total = (
        session.query(func.coalesce(func.sum(Invoice.amount), 0))
        .filter(
            Invoice.tenant_id == tenant_id,
            Invoice.lead_id == customer_id,
        )
        .scalar()
    ) or 0

    # Get tenant's total invoice amount
    tenant_total = (
        session.query(func.coalesce(func.sum(Invoice.amount), 0))
        .filter(
            Invoice.tenant_id == tenant_id,
        )
        .scalar()
    ) or 0

    # Normalize: customer_total / max(tenant_total, 1)
    denominator = max(tenant_total, 1)
    return customer_total / denominator
