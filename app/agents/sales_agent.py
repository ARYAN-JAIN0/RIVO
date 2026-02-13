# Sales Agent

"""
Sales Agent - Qualifies leads and progresses deals through pipeline

PHASE-3 EXTENSION: This agent runs AFTER SDR completes.
Trigger: Lead status = "Contacted" (from SDR approval)
Output: Deal created with qualification score

BACKWARD COMPATIBILITY:
- Reads from leads dictionary/object access (status="Contacted")
- Writes ONLY to deals table (never modifies leads table directly except status)
- Follows same pattern as SDR: gates → generation → scoring → approval/review
"""
import sys
from pathlib import Path

# Set PROJECT_ROOT directly (avoid circular imports from app.main)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import json
from datetime import datetime

from app.database.db_handler import (
    fetch_leads_by_status,
    create_deal,
    save_deal_review,
    mark_deal_decision
)
from app.services.llm_client import call_llm
from config.sdr_profile import SDR_NAME, SDR_COMPANY


# Configuration
QUALIFICATION_THRESHOLD = 85  # Same as SDR approval threshold
MIN_DEAL_VALUE = 10000  # Minimum deal size to pursue


def calculate_qualification_score(lead) -> tuple[int, list]:
    """
    BANT + MEDDIC scoring framework.
    Returns (Score 0-100, Breakdown)
    
    Budget (25): Can they afford it?
    Authority (20): Can they decide?
    Need (25): Do they have pain?
    Timeline (15): When do they need it?
    Champion (15): Do we have internal advocate?
    """
    score = 0
    reasons = []
    
    # Safe value extraction (ORM object access)
    company_size = str(getattr(lead, 'company_size', '')).lower()
    role = str(getattr(lead, 'role', '')).lower()
    insight = str(getattr(lead, 'verified_insight', '')).lower()
    industry = str(getattr(lead, 'industry', '')).lower()
    
    # 1. Budget (25 points) - Company size proxy
    if 'enterprise' in company_size or '1000+' in company_size:
        score += 25
        reasons.append("Enterprise budget (+25)")
    elif '500' in company_size or 'mid-market' in company_size:
        score += 20
        reasons.append("Mid-market budget (+20)")
    elif '100' in company_size:
        score += 10
        reasons.append("Small budget (+10)")
    
    # 2. Authority (20 points) - Decision maker level
    decision_makers = ['ceo', 'cto', 'cfo', 'founder', 'vp', 'head', 'director']
    if any(dm in role for dm in decision_makers):
        score += 20
        reasons.append("Decision maker authority (+20)")
    elif 'manager' in role:
        score += 10
        reasons.append("Manager authority (+10)")
    
    # 3. Need (25 points) - Pain signals
    pain_signals = ['hiring', 'growing', 'expanding', 'scaling', 'migration', 'urgent', 'struggling']
    if any(p in insight for p in pain_signals):
        score += 25
        reasons.append("Clear pain signal (+25)")
    elif 'looking' in insight or 'reviewing' in insight:
        score += 15
        reasons.append("Evaluating solutions (+15)")
    
    # 4. Timeline (15 points) - Urgency
    urgency_signals = ['immediate', 'urgent', 'q4', 'this quarter', 'asap', 'budget approved']
    if any(u in insight for u in urgency_signals):
        score += 15
        reasons.append("Urgent timeline (+15)")
    elif 'this year' in insight or 'soon' in insight:
        score += 10
        reasons.append("Near-term timeline (+10)")
    
    # 5. Champion (15 points) - Industry fit / Tech stack
    champion_industries = ['saas', 'tech', 'software', 'fintech']
    if any(ind in industry for ind in champion_industries):
        score += 15
        reasons.append("ICP industry fit (+15)")
    
    return min(score, 100), reasons


def estimate_deal_value(lead) -> int:
    """
    Estimate annual contract value based on company size.
    Conservative estimates to avoid over-promising.
    """
    company_size = str(getattr(lead, 'company_size', '')).lower()
    
    if 'enterprise' in company_size or '1000+' in company_size:
        return 100000  # $100k ACV
    elif '500' in company_size or 'mid-market' in company_size:
        return 50000   # $50k ACV
    elif '100' in company_size:
        return 25000   # $25k ACV
    else:
        return 10000   # $10k ACV (minimum)


def generate_qualification_notes(lead, score, reasons) -> str:
    """
    Generate LLM-powered qualification analysis.
    Falls back to deterministic notes if LLM unavailable.
    """
    name = str(getattr(lead, 'name', 'Prospect'))
    company = str(getattr(lead, 'company', 'Company'))
    role = str(getattr(lead, 'role', 'Role'))
    insight = str(getattr(lead, 'verified_insight', 'No insight'))
    
    prompt = f"""
You are a Sales Qualification Agent analyzing a lead.

Lead Details:
- Name: {name}
- Company: {company}
- Role: {role}
- Insight: {insight}
- BANT Score: {score}/100
- Breakdown: {', '.join(reasons)}

Task: Write a concise qualification assessment (50-100 words).
Include:
1. Key qualification factors
2. Recommended next steps
3. Potential objections to anticipate

Output JSON only:
{{
  "assessment": "Your analysis here...",
  "next_steps": "Recommended action...",
  "objections": "Potential blockers..."
}}
"""
    
    try:
        response = call_llm(prompt, json_mode=True)
        data = json.loads(response)
        
        notes = f"""
Assessment: {data.get('assessment', 'See breakdown')}

Next Steps: {data.get('next_steps', 'Schedule discovery call')}

Potential Objections: {data.get('objections', 'Budget, timeline')}

BANT Score: {score}/100
Breakdown: {', '.join(reasons)}
"""
        return notes.strip()
    
    except (json.JSONDecodeError, Exception) as e:
        # Deterministic fallback
        return f"""
Assessment: BANT Score {score}/100 based on company size, role authority, and verified insight signals.

Next Steps: Schedule discovery call to validate budget and timeline.

Potential Objections: Budget approval process, competing priorities.

Breakdown: {', '.join(reasons) if reasons else 'Low signal strength'}
"""


def run_sales_agent():
    """
    Main Sales Agent execution loop.
    
    Process:
    1. Fetch leads with status="Contacted" (SDR approved)
    2. Calculate qualification score (BANT + MEDDIC)
    3. Estimate deal value
    4. Generate qualification notes via LLM
    5. Auto-approve (≥85) or send for human review
    6. Create deal in deals table
    """
    # Fetch only leads that SDR successfully contacted
    contacted_leads = fetch_leads_by_status("Contacted")
    
    if not contacted_leads:
        print("No contacted leads to qualify.")
        return
    
    print(f"\n{'='*60}")
    print(f"💼 SALES AGENT: Processing {len(contacted_leads)} contacted leads")
    print(f"{'='*60}\n")
    
    for lead in contacted_leads:
        lead_id = lead.id
        name = str(getattr(lead, 'name', 'Prospect'))
        company = str(getattr(lead, 'company', ''))
        
        if not company:
            # Fallback for old data if needed, or error
            company = "Unknown Company"

        print(f"\n🔍 Qualifying Lead: {name} ({company})")
        
        # Step 1: Calculate BANT score
        qual_score, reasons = calculate_qualification_score(lead)
        print(f"📊 BANT Score: {qual_score}/100")
        if reasons:
            print(f"   Factors: {', '.join(reasons)}")
        
        # Step 2: Estimate deal value
        deal_value = estimate_deal_value(lead)
        print(f"💰 Estimated ACV: ${deal_value:,}")
        
        # Gate: Minimum deal value
        if deal_value < MIN_DEAL_VALUE:
            print(f"⚠️  Below minimum deal size (${MIN_DEAL_VALUE:,}) - Skipping")
            continue
        
        # Step 3: Generate qualification notes
        print("📝 Generating qualification assessment...")
        notes = generate_qualification_notes(lead, qual_score, reasons)
        
        # Step 4: Create deal
        deal_id = create_deal(
            lead_id=lead_id,
            company=company,
            acv=deal_value,
            qualification_score=qual_score,
            notes=notes,
            stage="qualified"
        )

        # Step 5: Auto-approval or human review
        if qual_score >= QUALIFICATION_THRESHOLD:
            print(f"✅ Auto-Approved (Score: {qual_score})")
            save_deal_review(deal_id, notes, qual_score, "Auto-Approved")
            mark_deal_decision(deal_id, "Approved")
        else:
            print(f"⚠️  Pending Review (Score: {qual_score} < {QUALIFICATION_THRESHOLD})")
            save_deal_review(deal_id, notes, qual_score, "Pending")
        
        print(f"💾 Deal #{deal_id} created")


if __name__ == "__main__":
    run_sales_agent()
