"""Sales agent: qualifies contacted leads and creates pending deal reviews."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.enums import DealStage, LeadStatus, ReviewStatus
from app.database.db_handler import create_deal, fetch_leads_by_status, save_deal_review
from app.services.llm_client import call_llm
from utils.validators import sanitize_text

logger = logging.getLogger(__name__)

QUALIFICATION_THRESHOLD = 85
MIN_DEAL_VALUE = 10_000


def calculate_qualification_score(lead) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    company_size = sanitize_text(str(getattr(lead, "company_size", ""))).lower()
    role = sanitize_text(str(getattr(lead, "role", ""))).lower()
    insight = sanitize_text(str(getattr(lead, "verified_insight", ""))).lower()
    industry = sanitize_text(str(getattr(lead, "industry", ""))).lower()

    if "enterprise" in company_size or "1000+" in company_size:
        score += 25
        reasons.append("enterprise_budget")
    elif "500" in company_size or "mid-market" in company_size:
        score += 20
        reasons.append("mid_market_budget")
    elif "100" in company_size:
        score += 10
        reasons.append("small_budget")

    if any(dm in role for dm in ["ceo", "cto", "cfo", "founder", "vp", "head", "director"]):
        score += 20
        reasons.append("decision_maker")
    elif "manager" in role:
        score += 10
        reasons.append("manager_level")

    if any(p in insight for p in ["hiring", "growing", "expanding", "scaling", "migration", "urgent", "struggling"]):
        score += 25
        reasons.append("clear_need")
    elif "looking" in insight or "reviewing" in insight:
        score += 15
        reasons.append("evaluating")

    if any(u in insight for u in ["immediate", "urgent", "q4", "this quarter", "asap", "budget approved"]):
        score += 15
        reasons.append("urgent_timeline")
    elif "this year" in insight or "soon" in insight:
        score += 10
        reasons.append("near_term")

    if any(ind in industry for ind in ["saas", "tech", "software", "fintech"]):
        score += 15
        reasons.append("industry_fit")

    return min(score, 100), reasons


def estimate_deal_value(lead) -> int:
    company_size = sanitize_text(str(getattr(lead, "company_size", ""))).lower()
    if "enterprise" in company_size or "1000+" in company_size:
        return 100_000
    if "500" in company_size or "mid-market" in company_size:
        return 50_000
    if "100" in company_size:
        return 25_000
    return 10_000


def generate_qualification_notes(lead, score: int, reasons: list[str]) -> str:
    name = sanitize_text(str(getattr(lead, "name", "Prospect")))
    company = sanitize_text(str(getattr(lead, "company", "Company")))
    role = sanitize_text(str(getattr(lead, "role", "Role")))
    insight = sanitize_text(str(getattr(lead, "verified_insight", "No insight")))

    prompt = f"""
You are a Sales Qualification Agent.
Lead:
- Name: {name}
- Company: {company}
- Role: {role}
- Insight: {insight}
- BANT Score: {score}/100
- Breakdown: {", ".join(reasons)}

Output JSON only:
{{
  "assessment": "Concise qualification assessment",
  "next_steps": "Recommended next steps",
  "objections": "Likely blockers"
}}
"""

    response = call_llm(prompt, json_mode=True)
    if response:
        try:
            data = json.loads(response)
            notes = (
                f"Assessment: {sanitize_text(data.get('assessment', 'See breakdown'))}\n\n"
                f"Next Steps: {sanitize_text(data.get('next_steps', 'Schedule discovery call'))}\n\n"
                f"Potential Objections: {sanitize_text(data.get('objections', 'Budget, timeline'))}\n\n"
                f"BANT Score: {score}/100\n"
                f"Breakdown: {', '.join(reasons)}"
            )
            return notes
        except json.JSONDecodeError:
            pass

    return (
        f"Assessment: BANT score {score}/100 based on company profile and verified signals.\n\n"
        "Next Steps: Schedule discovery call to validate budget and timeline.\n\n"
        "Potential Objections: Budget approval process, competing priorities.\n\n"
        f"Breakdown: {', '.join(reasons) if reasons else 'Low signal strength'}"
    )


def run_sales_agent() -> None:
    contacted_leads = fetch_leads_by_status(LeadStatus.CONTACTED.value)
    if not contacted_leads:
        logger.info("sales.no_contacted_leads", extra={"event": "sales.no_contacted_leads"})
        return

    logger.info("sales.start", extra={"event": "sales.start", "lead_count": len(contacted_leads)})
    for lead in contacted_leads:
        lead_id = lead.id
        company = sanitize_text(str(getattr(lead, "company", "")), max_len=300) or "Unknown Company"

        qualification_score, reasons = calculate_qualification_score(lead)
        deal_value = estimate_deal_value(lead)
        if deal_value < MIN_DEAL_VALUE:
            logger.info(
                "sales.lead.skipped_low_value",
                extra={"event": "sales.lead.skipped_low_value", "lead_id": lead_id, "deal_value": deal_value},
            )
            continue

        notes = generate_qualification_notes(lead, qualification_score, reasons)
        deal_id = create_deal(
            lead_id=lead_id,
            company=company,
            acv=deal_value,
            qualification_score=qualification_score,
            notes=notes,
            stage=DealStage.QUALIFIED.value,
        )

        # Human gate preserved: every deal stays pending until explicit dashboard action.
        save_deal_review(deal_id, notes, qualification_score, ReviewStatus.PENDING.value)
        logger.info(
            "sales.deal.created_pending_review",
            extra={
                "event": "sales.deal.created_pending_review",
                "deal_id": deal_id,
                "lead_id": lead_id,
                "score": qualification_score,
                "threshold": QUALIFICATION_THRESHOLD,
            },
        )

    logger.info("sales.complete", extra={"event": "sales.complete"})


if __name__ == "__main__":
    run_sales_agent()

