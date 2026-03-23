"""Smart Dunning System Module for payment collection automation.

This module provides intelligent dunning email generation with risk-based
tone selection and LLM-powered fallback to templates.
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any

from app.database.db import get_db_session
from app.database.models import Invoice, Lead
from app.services.llm_client import call_llm

logger = logging.getLogger(__name__)


# Predefined email templates for fallback
DUNNING_TEMPLATES = {
    "soft": "Dear {customer_name}, a friendly reminder that invoice #{invoice_number} for {amount} is due on {due_date}. Thank you for your attention.",
    "medium": "Dear {customer_name}, this is a reminder that invoice #{invoice_number} for {amount} was due on {due_date}. Please prioritize this payment.",
    "aggressive": "Dear {customer_name}, invoice #{invoice_number} for {amount} is overdue as of {due_date}. Immediate payment is required to avoid further action.",
}


def determine_dunning_tone(risk_score: float) -> str:
    """Determine the appropriate dunning tone based on risk score.

    Args:
        risk_score: A float between 0 and 1 representing payment risk.
            Higher values indicate higher risk of non-payment.

    Returns:
        String indicating the dunning tone: "soft", "medium", or "aggressive".
    """
    if risk_score < 0.3:
        return "soft"
    elif risk_score <= 0.7:
        return "medium"
    else:
        return "aggressive"


def should_send_reminder(tenant_id: int, customer_id: int, invoice_id: int) -> bool:
    """Check if a reminder should be sent for an overdue invoice.

    Simplified implementation: Returns True if the invoice is significantly
    overdue (more than 7 days past due date).

    Args:
        tenant_id: The tenant ID for multi-tenant isolation.
        customer_id: The customer (lead) ID.
        invoice_id: The invoice ID to check.

    Returns:
        Boolean: True if reminder should be sent, False otherwise.
    """
    try:
        with get_db_session() as session:
            invoice = (
                session.query(Invoice)
                .filter(
                    Invoice.tenant_id == tenant_id,
                    Invoice.id == invoice_id,
                    Invoice.lead_id == customer_id,
                )
                .first()
            )

            if not invoice:
                logger.warning(
                    "dunning.invoice_not_found",
                    extra={
                        "event": "dunning.invoice_not_found",
                        "tenant_id": tenant_id,
                        "invoice_id": invoice_id,
                    },
                )
                return False

            # Check if already paid
            if invoice.status in ("Paid", "Completed", "Closed"):
                return False

            # Get days overdue - use stored value or calculate from due_date
            days_overdue = invoice.days_overdue or 0

            if days_overdue == 0 and invoice.due_date:
                # Calculate from due_date if days_overdue not set
                if isinstance(invoice.due_date, date):
                    today = datetime.now().date()
                    if today > invoice.due_date:
                        days_overdue = (today - invoice.due_date).days

            # Send reminder if more than 7 days overdue
            return days_overdue > 7

    except Exception as e:
        logger.error(
            "dunning.should_send_reminder_error",
            extra={
                "event": "dunning.should_send_reminder_error",
                "tenant_id": tenant_id,
                "customer_id": customer_id,
                "invoice_id": invoice_id,
                "error": str(e),
            },
        )
        return False


def generate_dunning_email(tone: str, invoice_data: dict, risk_metrics: dict) -> str:
    """Generate a dunning email with LLM fallback to template strings.

    Args:
        tone: The dunning tone - "soft", "medium", or "aggressive".
        invoice_data: Dictionary containing invoice details:
            - customer_name: str
            - invoice_number: str
            - amount: str or number
            - due_date: str (date format)
        risk_metrics: Dictionary containing risk assessment metrics:
            - risk_score: float
            - on_time_ratio: float (optional)
            - avg_delay_days: float (optional)

    Returns:
        Generated email text string.
    """
    # Validate tone
    if tone not in DUNNING_TEMPLATES:
        logger.warning(
            "dunning.invalid_tone",
            extra={
                "event": "dunning.invalid_tone",
                "tone": tone,
            },
        )
        tone = "medium"

    # Try LLM generation first
    llm_email = _generate_email_with_llm(tone, invoice_data, risk_metrics)

    if llm_email:
        logger.info(
            "dunning.email_generated_llm",
            extra={
                "event": "dunning.email_generated_llm",
                "tone": tone,
            },
        )
        return llm_email

    # Fallback to template
    logger.info(
        "dunning.email_fallback_template",
        extra={
            "event": "dunning.email_fallback_template",
            "tone": tone,
        },
    )
    return _generate_email_from_template(tone, invoice_data)


def _generate_email_with_llm(
    tone: str, invoice_data: dict, risk_metrics: dict
) -> str | None:
    """Attempt to generate email using LLM.

    Args:
        tone: The dunning tone.
        invoice_data: Invoice details dictionary.
        risk_metrics: Risk metrics dictionary.

    Returns:
        Generated email string or None if LLM fails.
    """
    customer_name = invoice_data.get("customer_name", "Valued Customer")
    invoice_number = invoice_data.get("invoice_number", "N/A")
    amount = invoice_data.get("amount", "0")
    due_date = invoice_data.get("due_date", "N/A")

    # Build prompt for LLM
    prompt = f"""Generate a professional dunning email with the following details:
- Customer Name: {customer_name}
- Invoice Number: {invoice_number}
- Amount Due: {amount}
- Due Date: {due_date}
- Tone: {tone}
- Risk Score: {risk_metrics.get("risk_score", 0.5):.2f}

The email should be professional, clear, and appropriate for the specified tone.
Keep it concise and focused on encouraging payment.
"""

    response = call_llm(prompt, json_mode=False)

    if response:
        return response.strip()

    return None


def _generate_email_from_template(tone: str, invoice_data: dict) -> str:
    """Generate email from predefined template.

    Args:
        tone: The dunning tone.
        invoice_data: Invoice details dictionary.

    Returns:
        Formatted email string from template.
    """
    template = DUNNING_TEMPLATES.get(tone, DUNNING_TEMPLATES["medium"])

    # Format amount if it's numeric
    amount = invoice_data.get("amount", "0")
    if isinstance(amount, (int, float)):
        amount = f"${amount:,.2f}"

    return template.format(
        customer_name=invoice_data.get("customer_name", "Valued Customer"),
        invoice_number=invoice_data.get("invoice_number", "N/A"),
        amount=amount,
        due_date=invoice_data.get("due_date", "N/A"),
    )
