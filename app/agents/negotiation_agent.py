"""Negotiation agent: handles objections for approved proposals."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.enums import DealStage, ReviewStatus
from app.database.db_handler import (
    create_contract,
    fetch_deals_by_status,
    update_contract_negotiation,
)
from app.services.llm_client import call_llm
from app.utils.validators import sanitize_text

logger = logging.getLogger(__name__)

NEGOTIATION_APPROVAL_THRESHOLD = 85

OBJECTION_PLAYBOOK = {
    "price": {
        "pattern": ["expensive", "cost", "price", "budget", "afford"],
        "framework": "ROI justification with measurable business impact",
    },
    "timeline": {
        "pattern": ["time", "busy", "later", "next quarter", "delay"],
        "framework": "Cost-of-inaction framing with phased rollout",
    },
    "competitor": {
        "pattern": ["competitor", "already using", "signed with", "existing solution"],
        "framework": "Differentiation on outcome, not feature parity",
    },
    "authority": {
        "pattern": ["need approval", "talk to team", "not decision maker"],
        "framework": "Champion enablement with internal business case",
    },
    "trust": {
        "pattern": ["proven", "case study", "references", "risk"],
        "framework": "Risk mitigation via references and pilot scope",
    },
}


def classify_objections(objection_text: str) -> list[tuple[str, str]]:
    text = sanitize_text(objection_text).lower()
    identified: list[tuple[str, str]] = []
    for category, data in OBJECTION_PLAYBOOK.items():
        if any(pattern in text for pattern in data["pattern"]):
            identified.append((category, data["framework"]))
    return identified or [("general", "Clarify root concern via discovery questions")]


def generate_objection_response(deal, objections: str) -> tuple[str, int]:
    classified = classify_objections(objections)
    frameworks = [f"{cat}: {fw}" for cat, fw in classified]
    company = sanitize_text(str(getattr(deal, "company", "Company")))
    deal_value = int(getattr(deal, "acv", 50_000) or 50_000)

    prompt = f"""
You are a Senior Sales Negotiator.
Context:
- Company: {company}
- Deal Value: ${deal_value:,}
- Objections: {sanitize_text(objections)}
- Frameworks: {", ".join(frameworks)}

Output JSON only:
{{
  "strategy": "Multi-step objection handling strategy",
  "confidence": 85
}}
"""
    response = call_llm(prompt, json_mode=True)
    if response:
        try:
            data = json.loads(response)
            strategy = sanitize_text(data.get("strategy", ""))
            confidence = int(data.get("confidence", 0))
            if strategy:
                return strategy, max(0, min(confidence, 100))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    fallback = (
        "Use structured objection handling:\n"
        + "\n".join(
            f"{idx + 1}. Address {category}: {framework}"
            for idx, (category, framework) in enumerate(classified)
        )
    )
    return fallback, 60


def run_negotiation_agent() -> None:
    deals = fetch_deals_by_status(DealStage.PROPOSAL_SENT.value)
    if not deals:
        logger.info("negotiation.no_proposal_stage_deals", extra={"event": "negotiation.no_proposal_stage_deals"})
        return

    logger.info("negotiation.start", extra={"event": "negotiation.start", "deal_count": len(deals)})
    for deal in deals:
        deal_id = deal.id
        lead_id = deal.lead_id
        deal_value = int(getattr(deal, "acv", 0) or 0)

        if deal_value > 75_000:
            objections = (
                "Price is higher than expected. Need to justify ROI to CFO. "
                "Concerned about implementation timeline."
            )
        elif deal_value > 40_000:
            objections = "Budget is tight this quarter and two competitors are under evaluation."
        else:
            objections = "Need wider team buy-in and implementation clarity."

        strategy, confidence = generate_objection_response(deal, objections)
        contract_id = create_contract(
            deal_id=deal_id,
            lead_id=lead_id,
            contract_terms=f"Standard SaaS agreement - ${deal_value:,} ACV",
            contract_value=deal_value,
        )
        update_contract_negotiation(
            contract_id=contract_id,
            objections=objections,
            proposed_solutions=strategy,
            confidence_score=confidence,
        )

        logger.info(
            "negotiation.contract.updated_pending_review",
            extra={
                "event": "negotiation.contract.updated_pending_review",
                "deal_id": deal_id,
                "contract_id": contract_id,
                "confidence": confidence,
                "threshold": NEGOTIATION_APPROVAL_THRESHOLD,
                "review_status": ReviewStatus.PENDING.value,
            },
        )

    logger.info("negotiation.complete", extra={"event": "negotiation.complete"})


if __name__ == "__main__":
    run_negotiation_agent()

