# Negotiation Agent

"""
Negotiation Agent - Handles objections and progresses contracts

PHASE-3 EXTENSION: Runs after Sales Agent.
Trigger: Deal status = "Proposal Sent"
Output: Contract with objection handling strategies

BACKWARD COMPATIBILITY:
- Reads from deals.csv (stage="Proposal Sent")
- Writes ONLY to contracts.csv
- Same pattern: analysis → generation → scoring → approval/review
"""

import json
import pandas as pd
from datetime import datetime

from db.db_handler import (
    fetch_deals_by_status,
    create_contract,
    update_contract_negotiation,
    fetch_pending_contract_reviews
)
from app.services.llm_client import call_llm
from config.sdr_profile import SDR_NAME, SDR_COMPANY


# Configuration
NEGOTIATION_APPROVAL_THRESHOLD = 85


# Common objection patterns and response frameworks
OBJECTION_PLAYBOOK = {
    "price": {
        "pattern": ["expensive", "cost", "price", "budget", "afford"],
        "framework": "ROI Justification: Calculate cost savings or revenue uplift"
    },
    "timeline": {
        "pattern": ["time", "busy", "later", "next quarter", "delay"],
        "framework": "Cost of Inaction: Quantify current pain points"
    },
    "competitor": {
        "pattern": ["competitor", "already using", "signed with", "existing solution"],
        "framework": "Differentiation: Unique capabilities not available elsewhere"
    },
    "authority": {
        "pattern": ["need approval", "talk to team", "not decision maker"],
        "framework": "Champion Building: Equip them to sell internally"
    },
    "trust": {
        "pattern": ["proven", "case study", "references", "risk"],
        "framework": "Social Proof: Share similar customer success stories"
    }
}


def classify_objections(objection_text: str) -> list:
    """
    Classify objections into standard categories.
    Returns list of (category, framework) tuples.
    """
    objection_lower = objection_text.lower()
    identified = []
    
    for category, data in OBJECTION_PLAYBOOK.items():
        if any(pattern in objection_lower for pattern in data["pattern"]):
            identified.append((category, data["framework"]))
    
    return identified if identified else [("general", "Discovery: Ask probing questions to understand root cause")]


def generate_objection_response(deal, objections: str) -> tuple[str, int]:
    """
    Generate LLM-powered objection handling strategy.
    Returns (proposed_solutions, confidence_score)
    """
    # Classify objections
    classified = classify_objections(objections)
    frameworks = [f"{cat}: {fw}" for cat, fw in classified]
    
    company = str(deal.get('company', 'Company'))
    industry = str(deal.get('industry', 'Industry'))
    deal_value = deal.get('acv', 50000)
    
    prompt = f"""
You are a Senior Sales Negotiator handling objections.

Context:
- Company: {company}
- Industry: {industry}
- Deal Value: ${deal_value:,}
- Objections: {objections}

Identified Patterns: {', '.join(frameworks)}

Task: Create a response strategy that addresses each objection using the appropriate framework.

Requirements:
1. Acknowledge the concern genuinely
2. Provide data-driven response
3. Offer concrete next steps
4. Maintain collaborative tone

Output JSON only:
{{
  "strategy": "Your multi-point response strategy...",
  "confidence": 85
}}

Confidence Score (0-100):
- 90-100: Objection is superficial, easy to overcome
- 75-89: Standard objection with known responses
- 60-74: Complex objection requiring custom approach
- Below 60: Fundamental mismatch, likely to stall
"""
    
    try:
        response = call_llm(prompt, json_mode=True)
        data = json.loads(response)
        
        strategy = data.get('strategy', '')
        confidence = int(data.get('confidence', 0))
        
        # Add framework references
        full_response = f"""
OBJECTION HANDLING STRATEGY

{strategy}

FRAMEWORKS APPLIED:
{chr(10).join(f"- {cat.title()}: {fw}" for cat, fw in classified)}

RECOMMENDED NEXT STEPS:
1. Schedule follow-up call to address concerns in detail
2. Provide relevant case studies from similar {industry} companies
3. Offer proof-of-concept or pilot program
"""
        
        return full_response.strip(), min(max(confidence, 0), 100)
    
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️  LLM failed, using deterministic response: {e}")
        
        # Deterministic fallback
        fallback = f"""
OBJECTION HANDLING STRATEGY

Based on the objections raised, I recommend the following approach:

{chr(10).join(f"{i+1}. Address {cat} concern: {fw}" for i, (cat, fw) in enumerate(classified))}

NEXT STEPS:
1. Schedule discovery call to understand priorities
2. Share relevant case studies
3. Propose pilot program to reduce risk
"""
        return fallback.strip(), 60  # Medium confidence for fallback


def run_negotiation_agent():
    """
    Main Negotiation Agent execution loop.
    
    Process:
    1. Fetch deals with stage="Proposal Sent"
    2. Simulate objection gathering (in production: from CRM/email)
    3. Generate objection handling strategy
    4. Calculate confidence score
    5. Auto-approve (≥85) or send for human review
    6. Create/update contract in contracts.csv
    """
    # Fetch deals that need negotiation
    proposal_sent = fetch_deals_by_status("Proposal Sent")
    
    if proposal_sent.empty:
        print("No deals in proposal stage.")
        return
    
    print(f"\n{'='*60}")
    print(f"🤝 NEGOTIATION AGENT: Processing {len(proposal_sent)} deals")
    print(f"{'='*60}\n")
    
    for _, deal in proposal_sent.iterrows():
        deal_id = deal["deal_id"]
        lead_id = deal["lead_id"]
        
        print(f"\n🔍 Analyzing Deal #{deal_id}")
        
        # In production, objections would come from:
        # - Email parsing
        # - Sales rep notes
        # - Meeting transcripts
        # For now, simulate based on deal characteristics
        
        # Simulate objections based on deal value
        deal_value = deal.get('deal_value', 0)
        if deal_value > 75000:
            simulated_objections = "Price is higher than expected. Need to justify ROI to CFO. Also concerned about implementation timeline."
        elif deal_value > 40000:
            simulated_objections = "Budget is tight this quarter. Can we push to next quarter? Also evaluating 2 other vendors."
        else:
            simulated_objections = "Looks interesting but need to get team buy-in first. What's your implementation process?"
        
        print(f"📋 Objections: {simulated_objections[:80]}...")
        
        # Generate objection handling strategy
        print("💡 Generating response strategy...")
        proposed_solutions, confidence = generate_objection_response(deal, simulated_objections)
        
        print(f"📊 Confidence Score: {confidence}/100")
        
        # Create or update contract
        try:
            contract_id = create_contract(
                deal_id=deal_id,
                lead_id=lead_id,
                contract_terms=f"Standard SaaS Agreement - ${deal_value:,} ACV",
                contract_value=deal_value
            )
            
            update_contract_negotiation(
                contract_id=contract_id,
                objections=simulated_objections,
                proposed_solutions=proposed_solutions,
                confidence_score=confidence
            )
            
            if confidence >= NEGOTIATION_APPROVAL_THRESHOLD:
                print(f"✅ Auto-Approved (Confidence: {confidence})")
                print("   Strategy can be sent directly to prospect")
            else:
                print(f"⚠️  Pending Review (Confidence: {confidence} < {NEGOTIATION_APPROVAL_THRESHOLD})")
                print("   Requires senior sales review before sending")
            
            print(f"💾 Contract #{contract_id} created/updated")
            
        except Exception as e:
            print(f"❌ Error processing deal #{deal_id}: {e}")


if __name__ == "__main__":
    run_negotiation_agent()