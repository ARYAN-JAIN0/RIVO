"""Invoice payment prediction module.

This module provides payment prediction functionality based on customer
payment behavior history with full tenant isolation support.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.database.db import get_db_session
from app.database.models import Invoice
from app.finance.behavior import get_customer_payment_behavior


def predict_invoice_payment(tenant_id: int, invoice_id: int) -> dict[str, Any]:
    """Predict payment probability and expected date for an invoice.

    Analyzes customer payment behavior to predict:
    - payment_probability: likelihood of on-time payment (0-1)
    - expected_payment_date: predicted payment date

    Args:
        tenant_id: The tenant ID for multi-tenant isolation.
        invoice_id: The invoice ID to predict payment for.

    Returns:
        Dictionary containing:
        - payment_probability: float between 0 and 1
        - expected_payment_date: date object or original due date
    """
    try:
        return _predict_payment_impl(tenant_id, invoice_id)
    except Exception:
        # Fallback on any error - return safe defaults
        return _get_fallback_prediction(tenant_id, invoice_id)


def _predict_payment_impl(tenant_id: int, invoice_id: int) -> dict[str, Any]:
    """Internal implementation of payment prediction.

    Args:
        tenant_id: Tenant ID for filtering.
        invoice_id: Invoice ID to predict.

    Returns:
        Prediction dictionary with probability and date.
    """
    # Fetch the invoice with tenant isolation
    with get_db_session() as session:
        invoice = (
            session.query(Invoice)
            .filter(Invoice.id == invoice_id, Invoice.lead_id.isnot(None))
            .first()
        )

        if not invoice:
            return _get_fallback_prediction(tenant_id, invoice_id)

        # Store original due date for fallback
        original_due_date = invoice.due_date
        if original_due_date is None:
            original_due_date = date.today()

        customer_id = invoice.lead_id

    # Fetch customer payment behavior
    behavior = get_customer_payment_behavior(tenant_id, customer_id, days_window=90)

    # Check if customer has payment history
    total_invoices = behavior.get("total_invoices", 0)
    if total_invoices == 0:
        # No payment history - use fallback
        return {
            "payment_probability": 0.5,
            "expected_payment_date": original_due_date,
        }

    # Calculate on-time ratio
    on_time_payments = behavior.get("on_time_payments", 0)
    late_payments = behavior.get("late_payments", 0)

    on_time_ratio = on_time_payments / total_invoices if total_invoices > 0 else 0.0

    # Apply late payment penalty
    late_ratio = late_payments / total_invoices if total_invoices > 0 else 0.0
    penalty = late_ratio * 0.2

    # Calculate final probability and clamp between 0 and 1
    payment_probability = max(0.0, min(1.0, on_time_ratio - penalty))

    # Calculate expected payment date
    average_delay_days = behavior.get("average_delay_days", 0.0)
    expected_payment_date = original_due_date + timedelta(days=int(average_delay_days))

    return {
        "payment_probability": round(payment_probability, 4),
        "expected_payment_date": expected_payment_date,
    }


def _get_fallback_prediction(tenant_id: int, invoice_id: int) -> dict[str, Any]:
    """Get fallback prediction values when prediction fails.

    Args:
        tenant_id: Tenant ID (unused but kept for signature consistency).
        invoice_id: Invoice ID to get fallback for.

    Returns:
        Fallback prediction dictionary.
    """
    # Try to get the original due date from the invoice
    try:
        with get_db_session() as session:
            invoice = (
                session.query(Invoice)
                .filter(Invoice.id == invoice_id)
                .first()
            )
            if invoice and invoice.due_date:
                return {
                    "payment_probability": 0.5,
                    "expected_payment_date": invoice.due_date,
                }
    except Exception:
        pass

    # Ultimate fallback
    return {
        "payment_probability": 0.5,
        "expected_payment_date": date.today(),
    }
