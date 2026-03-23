"""Customer behavior model module for payment analytics.

This module provides customer payment behavior analysis based on invoice
and payment history, with full tenant isolation support.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.database.db import get_db_session
from app.database.models import Invoice


# Default fallback values for error cases
DEFAULT_BEHAVIOR = {
    "total_invoices": 0,
    "on_time_payments": 0,
    "late_payments": 0,
    "average_delay_days": 0.0,
}

# Minimum payments threshold for time-window analysis
MIN_PAYMENTS_THRESHOLD = 5


def get_customer_payment_behavior(
    tenant_id: int, customer_id: int, days_window: int = 90
) -> dict[str, Any]:
    """Analyze customer payment behavior within a time window.

    Queries payments within the specified time window (default 90 days).
    If fewer than 5 payments exist in the window, uses lifetime data as fallback.

    Args:
        tenant_id: The tenant ID for multi-tenant isolation.
        customer_id: The customer (lead) ID to analyze.
        days_window: Number of days to look back (default 90).

    Returns:
        Dictionary containing payment behavior metrics:
        - total_invoices: count of invoices with payments
        - on_time_payments: count where payment_date <= due_date
        - late_payments: count where payment_date > due_date
        - average_delay_days: average of positive delay values only
    """
    try:
        with get_db_session() as session:
            return _analyze_behavior_impl(session, tenant_id, customer_id, days_window)
    except Exception:
        # Fallback on any error - return safe defaults
        return DEFAULT_BEHAVIOR.copy()


def _analyze_behavior_impl(
    session: Session, tenant_id: int, customer_id: int, days_window: int
) -> dict[str, Any]:
    """Internal implementation of payment behavior analysis.

    Args:
        session: Database session.
        tenant_id: Tenant ID for filtering.
        customer_id: Customer (lead) ID.
        days_window: Number of days to look back.

    Returns:
        Behavior metrics dictionary.
    """
    # Calculate the cutoff date
    cutoff_date = datetime.utcnow() - timedelta(days=days_window)

    # First, try to get payments within the time window
    window_invoices = (
        session.query(Invoice)
        .filter(
            Invoice.tenant_id == tenant_id,
            Invoice.lead_id == customer_id,
            Invoice.payment_date.isnot(None),
            Invoice.due_date.isnot(None),
            Invoice.payment_date >= cutoff_date,
        )
        .all()
    )

    # If we have enough payments in the window, use them
    if len(window_invoices) >= MIN_PAYMENTS_THRESHOLD:
        return _calculate_behavior_metrics(window_invoices)

    # Fallback: use lifetime payment data
    lifetime_invoices = (
        session.query(Invoice)
        .filter(
            Invoice.tenant_id == tenant_id,
            Invoice.lead_id == customer_id,
            Invoice.payment_date.isnot(None),
            Invoice.due_date.isnot(None),
        )
        .all()
    )

    # If no payment history at all, return defaults
    if not lifetime_invoices:
        return DEFAULT_BEHAVIOR.copy()

    return _calculate_behavior_metrics(lifetime_invoices)


def _calculate_behavior_metrics(invoices: list[Invoice]) -> dict[str, Any]:
    """Calculate payment behavior metrics from invoice list.

    Args:
        invoices: List of Invoice objects with payment_date and due_date.

    Returns:
        Behavior metrics dictionary.
    """
    total_invoices = len(invoices)
    on_time_payments = 0
    late_payments = 0
    delay_days = []

    for inv in invoices:
        payment_date = inv.payment_date
        due_date = inv.due_date

        # Handle both datetime and date types
        if hasattr(payment_date, 'date'):
            payment_date = payment_date.date()
        if hasattr(due_date, 'date'):
            due_date = due_date.date()

        # Exact comparison: payment_date <= due_date is on_time
        if payment_date <= due_date:
            on_time_payments += 1
        else:
            late_payments += 1
            delay = (payment_date - due_date).days
            delay_days.append(delay)

    # Calculate average delay (only from late payments)
    average_delay_days = sum(delay_days) / len(delay_days) if delay_days else 0.0

    return {
        "total_invoices": total_invoices,
        "on_time_payments": on_time_payments,
        "late_payments": late_payments,
        "average_delay_days": round(average_delay_days, 2),
    }
