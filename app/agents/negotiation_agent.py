"""Negotiation agent: handles objections for approved proposals.

This agent manages the negotiation phase of the sales pipeline:
1. Processes deals in Proposal Sent stage
2. Generates objection handling strategies
3. Tracks negotiation turns to prevent infinite loops
4. Escalates to human review when needed

Key Features:
- MAX_NEGOTIATION_TURNS enforcement (prevents infinite negotiation)
- Confidence-based approval routing
- Objection classification with playbook frameworks
- Multi-tenant support via tenant_id

Thresholds:
- NEGOTIATION_APPROVAL_THRESHOLD: 85 (confidence for auto-approval)
- MAX_NEGOTIATION_TURNS: 3 (max negotiation rounds before escalation)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.enums import ContractStatus, DealStage, ReviewStatus
from app.database.db import get_db_session
from app.database.db_handler import (
    create_contract,
    fetch_contracts_by_status,
    fetch_deals_by_status,
    update_contract_negotiation,
)
from app.database.models import Contract
from app.services.llm_client import call_llm
from app.utils.validators import sanitize_text

logger = logging.getLogger(__name__)

# Thresholds
NEGOTIATION_APPROVAL_THRESHOLD = 85
MAX_NEGOTIATION_TURNS = 3  # Safety limit for negotiation rounds

# Objection handling playbook with patterns and frameworks
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
    """Classify objections into categories with handling frameworks.
    
    Args:
        objection_text: The raw objection text from the prospect.
        
    Returns:
        A list of tuples containing (category, framework) pairs.
    """
    text = sanitize_text(objection_text).lower()
    identified: list[tuple[str, str]] = []
    for category, data in OBJECTION_PLAYBOOK.items():
        if any(pattern in text for pattern in data["pattern"]):
            identified.append((category, data["framework"]))
    return identified or [("general", "Clarify root concern via discovery questions")]


def generate_objection_response(deal, objections: str) -> tuple[str, int]:
    """Generate an objection handling strategy using LLM.
    
    Args:
        deal: The deal object containing company and value info.
        objections: The objection text from the prospect.
        
    Returns:
        A tuple of (strategy_text, confidence_score).
    """
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
            # Safe confidence extraction with bounds checking
            raw_confidence = data.get("confidence", 0)
            confidence = max(0, min(int(raw_confidence), 100))
            if strategy:
                return strategy, confidence
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(
                "negotiation.confidence.parse_failed",
                extra={"event": "negotiation.confidence.parse_failed", "error": str(e)},
            )

    fallback = (
        "Use structured objection handling:\n"
        + "\n".join(
            f"{idx + 1}. Address {category}: {framework}"
            for idx, (category, framework) in enumerate(classified)
        )
    )
    return fallback, 60


def _has_signed_contract(deal_id: int) -> bool:
    """Check if a signed contract already exists for this deal.
    
    Args:
        deal_id: The deal ID to check.
        
    Returns:
        True if a signed contract exists, False otherwise.
    """
    signed_contracts = fetch_contracts_by_status(ContractStatus.SIGNED.value)
    return any(c.deal_id == deal_id for c in signed_contracts)


def _get_contract_by_deal(deal_id: int) -> Contract | None:
    """Get the contract for a deal if it exists.
    
    Args:
        deal_id: The deal ID to look up.
        
    Returns:
        The Contract object or None if not found.
    """
    with get_db_session() as session:
        return session.query(Contract).filter(Contract.deal_id == deal_id).first()


def _get_negotiation_turn(contract_id: int) -> int:
    """Get the current negotiation turn count for a contract.
    
    Args:
        contract_id: The contract ID to check.
        
    Returns:
        The number of negotiation turns so far.
    """
    with get_db_session() as session:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        return contract.negotiation_turn if contract and contract.negotiation_turn else 0


def _increment_negotiation_turn(contract_id: int) -> int:
    """Increment and return the negotiation turn count.
    
    Args:
        contract_id: The contract ID to update.
        
    Returns:
        The new negotiation turn count.
    """
    with get_db_session() as session:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.negotiation_turn = (contract.negotiation_turn or 0) + 1
            contract.last_updated = datetime.utcnow()
            session.commit()
            return contract.negotiation_turn
        return 0


def _is_max_turns_reached(contract_id: int) -> bool:
    """Check if the contract has reached maximum negotiation turns.
    
    Args:
        contract_id: The contract ID to check.
        
    Returns:
        True if max turns reached, False otherwise.
    """
    current_turn = _get_negotiation_turn(contract_id)
    return current_turn >= MAX_NEGOTIATION_TURNS


def run_negotiation_agent() -> None:
    """Run the negotiation agent for all deals in Proposal Sent stage.
    
    This function:
    1. Fetches all deals in Proposal Sent stage
    2. For each deal, checks if negotiation turn limit is reached
    3. Generates objection handling strategies
    4. Updates contract with negotiation details
    5. Routes to human review if max turns reached or low confidence
    """
    deals = fetch_deals_by_status(DealStage.PROPOSAL_SENT.value)
    if not deals:
        logger.info("negotiation.no_proposal_stage_deals", extra={"event": "negotiation.no_proposal_stage_deals"})
        return

    logger.info("negotiation.start", extra={"event": "negotiation.start", "deal_count": len(deals)})
    
    for deal in deals:
        deal_id = deal.id
        lead_id = deal.lead_id
        deal_value = int(getattr(deal, "acv", 0) or 0)
        tenant_id = getattr(deal, "tenant_id", 1)

        # Guard: Skip if signed contract already exists
        if _has_signed_contract(deal_id):
            logger.info(
                "negotiation.skip_signed_contract",
                extra={"event": "negotiation.skip_signed_contract", "deal_id": deal_id},
            )
            continue

        # Create or get existing contract
        contract_id = create_contract(
            deal_id=deal_id,
            lead_id=lead_id,
            contract_terms=f"Standard SaaS agreement - ${deal_value:,} ACV",
            contract_value=deal_value,
        )
        
        # Check if max negotiation turns reached
        if _is_max_turns_reached(contract_id):
            logger.warning(
                "negotiation.max_turns_reached",
                extra={
                    "event": "negotiation.max_turns_reached",
                    "deal_id": deal_id,
                    "contract_id": contract_id,
                    "max_turns": MAX_NEGOTIATION_TURNS,
                },
            )
            # Route to human review for escalation
            update_contract_negotiation(
                contract_id=contract_id,
                objections="Max negotiation turns reached - requires human escalation",
                proposed_solutions="Escalate to senior sales or account executive for manual intervention",
                confidence_score=0,
            )
            continue

        # Generate objections based on deal value (simulated for demo)
        if deal_value > 75_000:
            objections = (
                "Price is higher than expected. Need to justify ROI to CFO. "
                "Concerned about implementation timeline."
            )
        elif deal_value > 40_000:
            objections = "Budget is tight this quarter and two competitors are under evaluation."
        else:
            objections = "Need wider team buy-in and implementation clarity."

        # Generate objection response
        strategy, confidence = generate_objection_response(deal, objections)
        
        # Increment negotiation turn
        new_turn = _increment_negotiation_turn(contract_id)
        
        # Update contract with negotiation details
        update_contract_negotiation(
            contract_id=contract_id,
            objections=objections,
            proposed_solutions=strategy,
            confidence_score=confidence,
        )

        # Determine routing based on confidence and turn count
        if confidence >= NEGOTIATION_APPROVAL_THRESHOLD:
            review_status = ReviewStatus.APPROVED.value
            log_event = "negotiation.auto_approved"
        else:
            review_status = ReviewStatus.PENDING.value
            log_event = "negotiation.pending_review"

        logger.info(
            log_event,
            extra={
                "event": log_event,
                "deal_id": deal_id,
                "contract_id": contract_id,
                "confidence": confidence,
                "threshold": NEGOTIATION_APPROVAL_THRESHOLD,
                "turn": new_turn,
                "max_turns": MAX_NEGOTIATION_TURNS,
                "review_status": review_status,
            },
        )

    logger.info("negotiation.complete", extra={"event": "negotiation.complete"})


if __name__ == "__main__":
    run_negotiation_agent()
