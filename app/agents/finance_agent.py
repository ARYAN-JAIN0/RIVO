"""Finance agent: invoice creation and dunning draft generation."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.enums import ContractStatus, InvoiceStatus, ReviewStatus
from app.core.schemas import DunningGeneration, parse_schema
from app.database.db_handler import (
    create_invoice,
    fetch_all_invoices,
    fetch_contracts_by_status,
    save_dunning_draft,
    update_invoice_status,
)
from app.services.llm_client import call_llm
from config.sdr_profile import SDR_COMPANY, SDR_EMAIL, SDR_NAME
from utils.validators import sanitize_text

logger = logging.getLogger(__name__)

DUNNING_APPROVAL_THRESHOLD = 85
PAYMENT_TERMS_DAYS = 30

DUNNING_STAGES = {
    0: {"days": 0, "tone": "friendly_reminder", "subject": "Invoice Payment Confirmation"},
    1: {"days": 7, "tone": "polite_reminder", "subject": "Payment Due Reminder"},
    2: {"days": 14, "tone": "urgent_reminder", "subject": "Urgent: Payment Now Overdue"},
    3: {"days": 21, "tone": "final_notice", "subject": "Final Notice: Account Suspension Pending"},
    4: {"days": 30, "tone": "collections", "subject": "Account Suspended - Collections Process"},
}


def calculate_days_overdue(due_date_obj) -> int:
    if not due_date_obj:
        return 0
    try:
        if isinstance(due_date_obj, str):
            due_date = datetime.strptime(due_date_obj, "%Y-%m-%d").date()
        elif isinstance(due_date_obj, datetime):
            due_date = due_date_obj.date()
        else:
            due_date = due_date_obj
        delta = (datetime.utcnow().date() - due_date).days
        return max(0, delta)
    except (ValueError, AttributeError, TypeError):
        return 0


def determine_dunning_stage(days_overdue: int) -> int:
    if days_overdue >= 30:
        return 4
    if days_overdue >= 21:
        return 3
    if days_overdue >= 14:
        return 2
    if days_overdue >= 7:
        return 1
    return 0


def generate_dunning_email(invoice, stage_config: dict[str, str]) -> tuple[str, int]:
    company = sanitize_text(str(getattr(getattr(invoice, "lead", None), "company", "Customer")))
    amount = int(getattr(invoice, "amount", 0) or 0)
    invoice_id = getattr(invoice, "id", "INV-UNKNOWN")
    days_overdue = int(getattr(invoice, "days_overdue", 0) or 0)
    tone = stage_config["tone"]

    prompt = f"""
You are a Finance Operations Specialist writing a dunning email.
Context:
- Customer: {company}
- Invoice: #{invoice_id}
- Amount: ${amount:,}
- Days Overdue: {days_overdue}
- Tone: {tone}

Constraints:
- No placeholders
- <= 120 words
- Keep professional and factual

Output JSON only:
{{
  "email_body": "email body",
  "confidence": 85
}}
"""
    response = call_llm(prompt, json_mode=True).strip()
    if response:
        try:
            parsed = parse_schema(DunningGeneration, response)
            return sanitize_text(parsed.email_body, max_len=2000), int(parsed.confidence)
        except ValueError:
            pass

    fallback_templates = {
        "friendly_reminder": (
            f"Hi {company}, this is a friendly reminder that invoice #{invoice_id} for ${amount:,} "
            "is now due. If payment has already been sent, please ignore this note."
        ),
        "polite_reminder": (
            f"Following up on invoice #{invoice_id} for ${amount:,}, now {days_overdue} days past due. "
            "Please share payment timing or any issue we can help resolve."
        ),
        "urgent_reminder": (
            f"Our records show invoice #{invoice_id} (${amount:,}) is {days_overdue} days overdue. "
            "Please process payment promptly to avoid service disruption."
        ),
        "final_notice": (
            f"Final notice: invoice #{invoice_id} (${amount:,}) is {days_overdue} days overdue. "
            "Please remit payment within 7 days to prevent account restrictions."
        ),
        "collections": (
            f"Invoice #{invoice_id} (${amount:,}) remains unpaid after {days_overdue} days. "
            "This account has been escalated to collections. Contact finance immediately to resolve."
        ),
    }
    return fallback_templates.get(tone, fallback_templates["polite_reminder"]), 70


def inject_dunning_signature(body: str, invoice_id: int) -> str:
    return (
        f"{sanitize_text(body, max_len=4000)}\n\n"
        "Payment Options:\n"
        "- Online portal: https://payments.example.com\n"
        "- Wire transfer: available on request\n\n"
        f"Reference: Invoice #{invoice_id}\n\n"
        f"Best regards,\n"
        f"{SDR_NAME}\n"
        f"{SDR_COMPANY} Finance Team\n"
        f"{SDR_EMAIL}\n"
    )


def run_finance_agent() -> None:
    logger.info("finance.start", extra={"event": "finance.start"})
    signed_contracts = fetch_contracts_by_status(ContractStatus.SIGNED.value)
    all_invoices = fetch_all_invoices()
    existing_contract_ids = {inv.contract_id for inv in all_invoices}

    for contract in signed_contracts:
        contract_id = contract.id
        if contract_id in existing_contract_ids:
            continue

        amount = int(getattr(contract, "contract_value", 0) or 0)
        lead_id = contract.lead_id
        signed_date = getattr(contract, "signed_date", None) or datetime.utcnow()
        if isinstance(signed_date, str):
            try:
                signed_date = datetime.strptime(signed_date, "%Y-%m-%d")
            except ValueError:
                signed_date = datetime.utcnow()
        due_date = signed_date + timedelta(days=PAYMENT_TERMS_DAYS)
        invoice_id = create_invoice(
            contract_id=contract_id,
            lead_id=lead_id,
            amount=amount,
            due_date=due_date.strftime("%Y-%m-%d"),
        )
        logger.info(
            "finance.invoice.created",
            extra={"event": "finance.invoice.created", "invoice_id": invoice_id, "contract_id": contract_id},
        )

    all_invoices = fetch_all_invoices()
    unpaid = [inv for inv in all_invoices if inv.status in [InvoiceStatus.SENT.value, InvoiceStatus.OVERDUE.value]]
    for invoice in unpaid:
        invoice_id = invoice.id
        days_overdue = calculate_days_overdue(invoice.due_date)
        if days_overdue == 0:
            continue

        current_stage = int(getattr(invoice, "dunning_stage", 0) or 0)
        target_stage = determine_dunning_stage(days_overdue)
        if target_stage <= current_stage:
            continue

        stage_config = DUNNING_STAGES[target_stage]
        email_body, confidence = generate_dunning_email(invoice, stage_config)
        final_email = inject_dunning_signature(email_body, invoice_id)

        update_invoice_status(
            invoice_id=invoice_id,
            status=InvoiceStatus.OVERDUE.value,
            days_overdue=days_overdue,
            dunning_stage=target_stage,
        )
        save_dunning_draft(invoice_id=invoice_id, draft_message=final_email, confidence_score=confidence)
        logger.info(
            "finance.dunning.saved_pending_review",
            extra={
                "event": "finance.dunning.saved_pending_review",
                "invoice_id": invoice_id,
                "confidence": confidence,
                "threshold": DUNNING_APPROVAL_THRESHOLD,
                "review_status": ReviewStatus.PENDING.value,
            },
        )

    logger.info("finance.complete", extra={"event": "finance.complete"})


if __name__ == "__main__":
    run_finance_agent()

