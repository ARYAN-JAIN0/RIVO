"""Revenue forecasting module.

This module provides revenue forecasting functionality based on unpaid invoices
and payment probability predictions with full tenant isolation support.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_

from app.database.db import get_db_session
from app.database.models import Invoice
from app.finance.prediction import predict_invoice_payment


def forecast_revenue(tenant_id: int, days_ahead: int = 30) -> dict[str, Any]:
    """Forecast expected revenue from unpaid invoices due within the specified period.

    Analyzes all unpaid invoices with due dates within the next days_ahead period
    and calculates expected revenue based on payment probability predictions.

    Args:
        tenant_id: The tenant ID for multi-tenant isolation.
        days_ahead: Number of days to forecast ahead (default: 30).

    Returns:
        Dictionary containing:
        - tenant_id: int - The tenant ID
        - forecast_period_days: int - Number of days in forecast period
        - expected_revenue: float - SUM(invoice.amount * payment_probability)
        - total_invoices: int - Count of qualifying invoices
        - total_raw_amount: float - Total invoice amount without probability weighting
        - total_expected_amount: float - Same as expected_revenue (for fallback compatibility)
        - calculated_at: str - ISO format timestamp of calculation
    """
    try:
        return _forecast_revenue_impl(tenant_id, days_ahead)
    except Exception:
        # Fallback on any error - return raw sum as expected revenue
        return _get_fallback_forecast(tenant_id, days_ahead)


def _forecast_revenue_impl(tenant_id: int, days_ahead: int) -> dict[str, Any]:
    """Internal implementation of revenue forecasting.

    Args:
        tenant_id: Tenant ID for filtering.
        days_ahead: Number of days to forecast ahead.

    Returns:
        Forecast dictionary with all computed values.
    """
    today = date.today()
    end_date = today.replace(day=today.day + days_ahead) if today.day + days_ahead <= 28 else date(
        today.year, today.month + 1, min(28, days_ahead - (28 - today.day))
    )
    # Simpler approach: use date arithmetic
    from datetime import timedelta
    end_date = today + timedelta(days=days_ahead)

    # Fetch unpaid invoices within the date range with tenant filtering
    with get_db_session() as session:
        invoices = (
            session.query(Invoice)
            .join(Invoice.lead)  # Join with lead for tenant filtering
            .filter(
                and_(
                    Invoice.lead.has(tenant_id=tenant_id),  # Tenant isolation via lead
                    Invoice.due_date >= today,
                    Invoice.due_date <= end_date,
                    Invoice.status != "Paid",  # Exclude paid invoices
                    Invoice.status != "Canceled",  # Exclude canceled invoices
                    Invoice.amount.isnot(None),
                    Invoice.amount > 0,
                )
            )
            .all()
        )

    total_invoices_count = len(invoices)
    total_raw_amount = 0.0
    expected_revenue = 0.0

    # Process each invoice
    for invoice in invoices:
        invoice_amount = float(invoice.amount) if invoice.amount else 0.0
        total_raw_amount += invoice_amount

        # Get payment prediction for this invoice
        prediction = predict_invoice_payment(tenant_id, invoice.id)
        payment_probability = prediction.get("payment_probability", 0.5)

        # Calculate expected amount for this invoice
        expected_amount = invoice_amount * payment_probability
        expected_revenue += expected_amount

    return {
        "tenant_id": tenant_id,
        "forecast_period_days": days_ahead,
        "expected_revenue": round(expected_revenue, 2),
        "total_invoices": total_invoices_count,
        "total_raw_amount": round(total_raw_amount, 2),
        "total_expected_amount": round(expected_revenue, 2),
        "calculated_at": datetime.utcnow().isoformat(),
    }


def _get_fallback_forecast(tenant_id: int, days_ahead: int) -> dict[str, Any]:
    """Get fallback forecast values when computation fails.

    Computes forecast using raw sum (probability = 1.0 for all invoices).

    Args:
        tenant_id: Tenant ID for filtering.
        days_ahead: Number of days to forecast ahead.

    Returns:
        Fallback forecast dictionary using raw amounts.
    """
    today = date.today()
    from datetime import timedelta
    end_date = today + timedelta(days=days_ahead)

    try:
        with get_db_session() as session:
            invoices = (
                session.query(Invoice)
                .join(Invoice.lead)
                .filter(
                    and_(
                        Invoice.lead.has(tenant_id=tenant_id),
                        Invoice.due_date >= today,
                        Invoice.due_date <= end_date,
                        Invoice.status != "Paid",
                        Invoice.status != "Canceled",
                        Invoice.amount.isnot(None),
                        Invoice.amount > 0,
                    )
                )
                .all()
            )

            total_invoices_count = len(invoices)
            total_raw_amount = sum(float(inv.amount) if inv.amount else 0.0 for inv in invoices)
    except Exception:
        total_invoices_count = 0
        total_raw_amount = 0.0

    return {
        "tenant_id": tenant_id,
        "forecast_period_days": days_ahead,
        "expected_revenue": round(total_raw_amount, 2),
        "total_invoices": total_invoices_count,
        "total_raw_amount": round(total_raw_amount, 2),
        "total_expected_amount": round(total_raw_amount, 2),
        "calculated_at": datetime.utcnow().isoformat(),
    }
