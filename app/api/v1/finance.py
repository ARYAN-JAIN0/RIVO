"""Finance API endpoints for risk scoring and revenue forecasting."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.api._compat import APIRouter, Header, HTTPException, Query, status
from app.api.v1._authz import authorize, map_auth_error
from app.finance.forecasting import forecast_revenue
from app.finance.scoring import calculate_customer_risk_score

router = APIRouter(prefix="/finance", tags=["finance"])


def _authorize(authorization: str | None, scopes: list[str]):
    """Helper to authorize requests."""
    try:
        return authorize(authorization=authorization, scopes=scopes)
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc


@router.get("/risk/{customer_id}")
def get_customer_risk(
    customer_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """Calculate payment risk score for a customer.

    Risk scoring endpoints require 'finance.risk.read' scope.
    Tenant ID is derived from the authenticated user context.
    """
    user = _authorize(authorization, scopes=["finance.risk.read"])
    tenant_id = user.tenant_id
    """Calculate payment risk score for a customer.

    Computes risk score based on payment history metrics including:
    - on_time_ratio: percentage of payments made on or before due date
    - avg_delay_days: average delay for late payments
    - max_delay_days: maximum delay for late payments

    Risk score formula combines these metrics with deal size normalization.

    Args:
        customer_id: The customer (lead) ID to calculate risk for.
        tenant_id: The tenant ID for multi-tenant isolation.

    Returns:
        Dictionary containing risk score and related metrics:
        - customer_id: int - The customer ID
        - risk_score: float - Risk score (0-1, higher = more risky)
        - on_time_ratio: float - Percentage of on-time payments (0-1)
        - avg_delay_days: float - Average delay in days
        - max_delay_days: int - Maximum delay in days
        - total_payments: int - Total number of payments
        - on_time_payments: int - Number of on-time payments
        - calculated_at: str - ISO format timestamp of calculation
    """
    result = calculate_customer_risk_score(tenant_id, customer_id)
    result["customer_id"] = customer_id
    result["calculated_at"] = datetime.utcnow().isoformat()
    return result


@router.get("/forecast")
def get_revenue_forecast(
    authorization: str | None = Header(default=None, alias="Authorization"),
    days: int = Query(30, ge=1, le=365, description="Number of days to forecast ahead"),
) -> dict[str, Any]:
    """Forecast expected revenue from unpaid invoices.

    Revenue forecasting endpoints require 'finance.forecast.read' scope.
    Tenant ID is derived from the authenticated user context.
    """
    user = _authorize(authorization, scopes=["finance.forecast.read"])
    tenant_id = user.tenant_id
    """Forecast expected revenue from unpaid invoices.

    Analyzes all unpaid invoices with due dates within the specified period
    and calculates expected revenue based on payment probability predictions.

    Args:
        tenant_id: The tenant ID for multi-tenant isolation.
        days: Number of days to forecast ahead (default: 30, range: 1-365).

    Returns:
        Dictionary containing forecast metrics:
        - tenant_id: int - The tenant ID
        - forecast_period_days: int - Number of days in forecast period
        - expected_revenue: float - SUM(invoice.amount * payment_probability)
        - total_invoices: int - Count of qualifying invoices
        - total_raw_amount: float - Total invoice amount without probability weighting
        - calculated_at: str - ISO format timestamp of calculation
    """
    result = forecast_revenue(tenant_id, days_ahead=days)
    result["calculated_at"] = datetime.utcnow().isoformat()
    return result
