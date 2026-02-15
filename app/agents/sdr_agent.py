from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.enums import LeadStatus, ReviewStatus
from app.core.schemas import SDREmailEvaluation, SDREmailGeneration, parse_schema
from app.database.db_handler import (
    fetch_leads_by_status,
    get_prompt_template,
    log_llm_interaction,
    mark_review_decision,
    save_draft,
    update_lead_signal_score,
    update_lead_status,
)
from app.services.email_service import EmailService

from app.services.llm_client import call_llm
from config.sdr_profile import SDR_COMPANY, SDR_EMAIL, SDR_NAME, SDR_ROLE
from app.utils.validators import deterministic_email_quality_score, sanitize_text, validate_structure

logger = logging.getLogger(__name__)

APPROVAL_THRESHOLD = 85
AUTO_SEND_THRESHOLD = 92
SIGNAL_THRESHOLD = 60
PROMPT_VERSION = "sdr-v2.0"


def safe_str(val: object | None) -> str:
    return sanitize_text("" if val is None else str(val), max_len=2000)


def check_negative_gate(lead) -> tuple[bool, str]:
    neg_signals = safe_str(getattr(lead, "negative_signals", "")).lower()
    industry = safe_str(getattr(lead, "industry", "")).lower()
    last_contacted = getattr(lead, "last_contacted", None)

    if "layoff" in neg_signals:
        return True, "Recent layoffs detected"
    if "competitor" in neg_signals:
        return True, "Competitor lock-in risk"

    forbidden_sectors = ["government", "academic", "education", "non-profit", "ngo"]
    if any(sec in industry for sec in forbidden_sectors):
        return True, "High-risk outreach sector"

    if last_contacted:
        try:
            last_date = (
                datetime.strptime(last_contacted, "%Y-%m-%d")
                if isinstance(last_contacted, str)
                else last_contacted
            )
            delta = (datetime.utcnow() - last_date).days
            if delta < 30:
                return True, f"Recently contacted ({delta} days ago)"
        except (ValueError, TypeError):
            pass

    return False, ""


def calculate_signal_score(lead) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    insight = safe_str(getattr(lead, "verified_insight", "")).lower()
    role = safe_str(getattr(lead, "role", "")).lower()
    size = safe_str(getattr(lead, "company_size", "")).lower()

    if any(k in insight for k in ["hiring", "growing", "expanding"]):
        score += 30
        reasons.append("growth-signal")
    if any(k in insight for k in ["tech", "install", "stack", "migration"]):
        score += 25
        reasons.append("tech-change")
    if any(dm in role for dm in ["cto", "ceo", "vp", "head", "director", "founder", "ciso"]):
        score += 20
        reasons.append("decision-maker")
    if any(k in size for k in ["1000", "500", "enterprise", "mid-market"]):
        score += 15
        reasons.append("icp-fit")
    if any(k in insight for k in ["budget", "q4", "immediate"]):
        score += 10
        reasons.append("urgency")

    return min(score, 100), reasons


def build_fallback_email_body(lead) -> str:
    name = safe_str(getattr(lead, "name", "there"))
    company = safe_str(getattr(lead, "company", "your team"))
    industry = safe_str(getattr(lead, "industry", "your industry"))
    insight = safe_str(getattr(lead, "verified_insight", "recent operational changes"))

    return (
        f"Hi {name}, I noticed {company} is seeing {insight} in {industry}. "
        "We help teams shorten rollout time and improve revenue visibility without adding process overhead. "
        "Would you be open to a quick 15-minute call next week to compare approaches?"
    )


def _generation_prompt(lead) -> str:
    name = safe_str(getattr(lead, "name", "Prospect"))
    company = safe_str(getattr(lead, "company", "your company"))
    industry = safe_str(getattr(lead, "industry", "your industry"))
    insight = safe_str(getattr(lead, "verified_insight", f"recent trends in {industry}"))
    default_template = f"""
You are an expert SDR Agent.
Prompt Version: {PROMPT_VERSION}
Context:
- Prospect: {name} ({company})
- Industry: {industry}
- Insight: {insight}
- My Role: {SDR_ROLE} at {SDR_COMPANY}

Task: Write a cold email body (NO signature), 45-90 words, concrete and specific.
Output JSON only:
{{
  "thought_process": "Why this angle fits this lead",
  "email_body": "Email body only"
}}
"""
    return get_prompt_template("sdr", "cold_email_generation", default_template)


def generate_email_body(lead) -> str:
    prompt = _generation_prompt(lead)
    response_text = call_llm(prompt, json_mode=True).strip()
    log_llm_interaction("sdr", prompt, response_text, tenant_id=getattr(lead, "tenant_id", 1), lead_id=getattr(lead, "id", None))
    if not response_text:
        return build_fallback_email_body(lead)

    try:
        parsed = parse_schema(SDREmailGeneration, response_text)
        return safe_str(parsed.email_body) or build_fallback_email_body(lead)
    except ValueError:
        repair_prompt = (
            "Return valid JSON matching keys thought_process and email_body only. "
            f"Original output:\n{response_text}"
        )
        repaired = call_llm(repair_prompt, json_mode=True).strip()
        try:
            parsed = parse_schema(SDREmailGeneration, repaired)
            return safe_str(parsed.email_body) or build_fallback_email_body(lead)
        except ValueError:
            # Final fallback: attempt plain json parse, otherwise deterministic.
            try:
                data = json.loads(response_text)
                return safe_str(data.get("email_body", "")) or build_fallback_email_body(lead)
            except json.JSONDecodeError:
                return build_fallback_email_body(lead)


def inject_signature(body: str) -> str:
    clean_body = sanitize_text(body).replace("[Signature]", "").strip()
    return (
        f"{clean_body}\n\n"
        f"Best regards,\n"
        f"{SDR_NAME}\n"
        f"{SDR_ROLE}, {SDR_COMPANY}\n"
        f"{SDR_EMAIL}"
    )


def evaluate_email(email_text: str, lead) -> int:
    deterministic_score = deterministic_email_quality_score(
        email_text=email_text,
        company=safe_str(getattr(lead, "company", "")),
        industry=safe_str(getattr(lead, "industry", "")),
    )
    prompt = f"""
You are a Senior Sales Manager. Review this email draft and score 0-100.
Output JSON only:
{{
  "critique": "short critique",
  "score": 85
}}

Email:
{email_text}
"""
    llm_score = 0
    response = call_llm(prompt, json_mode=True).strip()
    log_llm_interaction("sdr", prompt, response, tenant_id=getattr(lead, "tenant_id", 1), lead_id=getattr(lead, "id", None))
    if response:
        try:
            parsed = parse_schema(SDREmailEvaluation, response)
            llm_score = int(parsed.score)
        except ValueError:
            llm_score = 0

    # Weighted blend to reduce single-model self-evaluation bias.
    final_score = int(round((deterministic_score * 0.6) + (llm_score * 0.4)))
    return max(0, min(final_score, 100))


def run_sdr_agent() -> None:
    leads = fetch_leads_by_status(LeadStatus.NEW.value)
    if not leads:
        logger.info("sdr.no_new_leads", extra={"event": "sdr.no_new_leads"})
        return

    logger.info("sdr.start", extra={"event": "sdr.start", "lead_count": len(leads)})

    for lead in leads:
        lead_id = lead.id
        logger.info("sdr.lead.start", extra={"event": "sdr.lead.start", "lead_id": lead_id})

        blocked, reason = check_negative_gate(lead)
        if blocked:
            update_lead_status(lead_id, LeadStatus.DISQUALIFIED.value)
            mark_review_decision(lead_id, ReviewStatus.BLOCKED.value, actor="system")
            logger.info(
                "sdr.lead.blocked",
                extra={"event": "sdr.lead.blocked", "lead_id": lead_id, "reason": reason},
            )
            continue

        signal_score, reasons = calculate_signal_score(lead)
        update_lead_signal_score(lead_id, signal_score)
        logger.info(
            "sdr.signal_score",
            extra={"event": "sdr.signal_score", "lead_id": lead_id, "score": signal_score, "reasons": ",".join(reasons)},
        )

        if signal_score < SIGNAL_THRESHOLD:
            update_lead_status(lead_id, LeadStatus.DISQUALIFIED.value)
            mark_review_decision(lead_id, ReviewStatus.SKIPPED.value, actor="system")
            logger.info(
                "sdr.lead.skipped_low_signal",
                extra={"event": "sdr.lead.skipped_low_signal", "lead_id": lead_id, "score": signal_score},
            )
            continue

        body = generate_email_body(lead)
        final_email = inject_signature(body)

        if not validate_structure(final_email):
            save_draft(lead_id, final_email, 0, ReviewStatus.STRUCTURAL_FAILED.value)
            logger.warning(
                "sdr.lead.structural_failed",
                extra={"event": "sdr.lead.structural_failed", "lead_id": lead_id},
            )
            continue

        score = evaluate_email(final_email, lead)
        if score >= AUTO_SEND_THRESHOLD:
            email_service = EmailService()
            sent = email_service.send_email(
                tenant_id=getattr(lead, "tenant_id", 1),
                lead_id=lead_id,
                to_email=safe_str(getattr(lead, "email", "")),
                subject=f"Quick idea for {safe_str(getattr(lead, 'company', 'your team'))}",
                html_body=f"<p>{final_email.replace(chr(10), '<br/>')}</p>",
                text_body=final_email,
            )
            save_draft(lead_id, final_email, score, ReviewStatus.APPROVED.value if sent else ReviewStatus.PENDING.value)
            if sent:
                update_lead_status(lead_id, LeadStatus.CONTACTED.value)
            logger.info(
                "sdr.lead.auto_send_evaluated",
                extra={"event": "sdr.lead.auto_send_evaluated", "lead_id": lead_id, "score": score, "sent": sent},
            )
        else:
            save_draft(lead_id, final_email, score, ReviewStatus.PENDING.value)
            logger.info(
                "sdr.lead.draft_saved",
                extra={"event": "sdr.lead.draft_saved", "lead_id": lead_id, "score": score, "approval_threshold": APPROVAL_THRESHOLD},
            )

    logger.info("sdr.complete", extra={"event": "sdr.complete"})


if __name__ == "__main__":
    run_sdr_agent()
