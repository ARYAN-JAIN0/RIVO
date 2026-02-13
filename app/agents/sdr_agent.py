import json
import re
import sys
from pathlib import Path
from datetime import datetime

# Set PROJECT_ROOT directly (avoid circular imports from app.main)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Updated imports for ORM-based db_handler
from app.database.db_handler import (
    fetch_leads_by_status,  # Was fetch_new_leads
    update_lead_status,
    save_draft,
    mark_review_decision,
    update_lead_signal_score
)
from app.services.llm_client import call_llm
from config.sdr_profile import (
    SDR_NAME,
    SDR_COMPANY,
    SDR_ROLE,
    SDR_EMAIL
)

# Configuration
APPROVAL_THRESHOLD = 85
SIGNAL_THRESHOLD = 60

# -------------------------------------------------
# 0. UTILITY & SAFETY HELPERS
# -------------------------------------------------

def safe_str(val) -> str:
    """Safely converts values (None, etc) to empty string."""
    if val is None:
        return ""
    return str(val).strip()

# -------------------------------------------------
# 1. SIGNAL & GATE LOGIC (DETERMINISTIC ROI)
# -------------------------------------------------

def check_negative_gate(lead) -> tuple[bool, str]:
    """
    Gate 1: Hard blocks. Returns (IsBlocked, Reason).
    Checks for layoffs, competitors, high-risk sectors, or recent contact.
    """
    # ORM object access
    neg_signals = safe_str(getattr(lead, 'negative_signals', '')).lower()
    industry = safe_str(getattr(lead, 'industry', '')).lower()
    last_contacted = getattr(lead, 'last_contacted', None)

    # 1. Critical Business Risks
    if 'layoff' in neg_signals:
        return True, "Recent Layoffs detected"
    if 'competitor' in neg_signals:
        return True, "Competitor signed recently"

    # 2. Sector Risks (Cold outreach to these is often flagged)
    forbidden_sectors = ['government', 'academic', 'education', 'non-profit', 'ngo']
    if any(sec in industry for sec in forbidden_sectors):
        return True, "High-Risk Sector (Gov/Edu)"

    # 3. Frequency Cap (Prevent spamming)
    if last_contacted:
        try:
            # last_contacted is likely a datetime object from ORM
            if isinstance(last_contacted, str):
                last_date = datetime.strptime(last_contacted, '%Y-%m-%d')
            else:
                last_date = last_contacted
                
            delta = (datetime.now() - last_date).days
            if delta < 30:
                return True, f"Contacted {delta} days ago (<30 limit)"
        except (ValueError, TypeError):
            # If date is malformed, ignore it (safer than crashing)
            pass

    return False, ""


def calculate_signal_score(lead) -> tuple[int, list]:
    """
    Gate 2: Signal Strength. Returns (Score, BreakdownList).
    """
    score = 0
    reasons = []
    
    insight = safe_str(getattr(lead, 'verified_insight', '')).lower()
    role = safe_str(getattr(lead, 'role', '')).lower()
    size = safe_str(getattr(lead, 'company_size', '')).lower()
    
    # 1. Intent Signals (+30 / +25)
    if 'hiring' in insight or 'growing' in insight or 'expanding' in insight:
        score += 30
        reasons.append("Hiring/Growth (+30)")
    if 'tech' in insight or 'install' in insight or 'stack' in insight or 'migration' in insight:
        score += 25
        reasons.append("Tech/Install Signal (+25)")
        
    # 2. Decision Maker Authority (+20)
    decision_makers = ['cto', 'ceo', 'vp', 'head', 'director', 'founder', 'ciso']
    if any(dm in role for dm in decision_makers):
        score += 20
        reasons.append("Decision Maker (+20)")
        
    # 3. ICP Fit (+15)
    # Assumes target is mid-market to enterprise
    if any(k in size for k in ['1000', '500', 'enterprise', 'mid-market']):
        score += 15
        reasons.append("ICP Company Size (+15)")
        
    # 4. Budget/Urgency (+10)
    if 'budget' in insight or 'q4' in insight or 'immediate' in insight:
        score += 10
        reasons.append("Budget/Urgency (+10)")
        
    return min(score, 100), reasons

# -------------------------------------------------
# 2. STRUCTURAL VALIDATION (STRICT)
# -------------------------------------------------

def validate_structure(email_text: str) -> bool:
    if not email_text or not isinstance(email_text, str):
        return False

    text = email_text.strip().lower()

    # 1. Check for fatal placeholders
    forbidden = ["[your name]", "[your company]", "{name}", "{company}", "sincerely, [name]"]
    for f in forbidden:
        if f in text:
            return False

    # 2. Valid Ending Check
    # Must end with the injected email OR a standard signoff
    valid_endings = ("best,", "regards,", "sincerely,", "thanks,")
    
    has_valid_ending = False
    if "@" in text.split()[-1]: # Ends with email address (Standard Injection)
        has_valid_ending = True
    elif any(text.endswith(s) for s in valid_endings): # Ends with text signoff
        has_valid_ending = True
        
    if not has_valid_ending:
        return False

    # 3. Minimum Length (Optimized for 7B models)
    if len(text.split()) < 30:
        return False

    return True

# -------------------------------------------------
# 3. GENERATION (CHAIN-OF-THOUGHT)
# -------------------------------------------------



def build_fallback_email_body(lead) -> str:
    """Deterministic fallback when LLM is unavailable or times out."""
    name = safe_str(getattr(lead, 'name', 'there'))
    company = safe_str(getattr(lead, 'company', 'your team'))
    industry = safe_str(getattr(lead, 'industry', 'your industry'))
    insight = safe_str(getattr(lead, 'verified_insight', 'recent operational changes'))

    return (
        f"Hi {name}, I noticed {company} is seeing {insight} in {industry}. "
        f"We help teams shorten rollout time and improve pipeline visibility without adding overhead. "
        f"Would you be open to a quick 15-minute call next week to compare approaches?"
    )

def generate_email_body(lead):
    name = safe_str(getattr(lead, 'name', 'Prospect'))
    company = safe_str(getattr(lead, 'company', 'your company'))
    industry = safe_str(getattr(lead, 'industry', 'your industry'))
    insight = safe_str(getattr(lead, 'verified_insight', f'recent trends in {industry}'))

    prompt = f"""
You are an expert SDR Agent. 
Context:
- Prospect: {name} ({company})
- Industry: {industry}
- Insight: {insight}
- My Role: {SDR_ROLE} at {SDR_COMPANY} (B2B SaaS)

Task: Write a cold email (NO signature).
Goal: 85+/100 score. Must be specific, not generic.

Instructions:
1. Analyze the insight and how our product helps.
2. Draft a concise email (45-75 words).
3. Output JSON ONLY.

Format:
{{
  "thought_process": "Briefly explain why this angle works...",
  "email_body": "The actual email text here..."
}}
"""
    # Requires updated llm_client.py with json_mode support
    response_text = call_llm(prompt, json_mode=True).strip()

    if not response_text:
        print("⚠️ Using deterministic fallback email body due to LLM timeout/unavailability.")
        return build_fallback_email_body(lead)

    try:
        data = json.loads(response_text)
        email_body = safe_str(data.get("email_body", ""))
        return email_body or build_fallback_email_body(lead)
    except json.JSONDecodeError:
        return response_text

def inject_signature(body: str) -> str:
    # Cleanup potential double signatures from LLM
    clean_body = body.replace("[Signature]", "").replace("Best regards,", "").strip()
    return f"""{clean_body}

Best regards,
{SDR_NAME}
{SDR_ROLE}, {SDR_COMPANY}
{SDR_EMAIL}"""

# -------------------------------------------------
# 4. EVALUATION
# -------------------------------------------------

def evaluate_email(email_text: str) -> int:
    prompt = f"""
You are a Senior Sales Manager. Review this email draft.

Email:
"{email_text}"

Rubric:
- 90-100: Highly personalized, mentions specific company/industry details, distinct value prop.
- 75-89: Good structure, but slightly generic value.
- 0-74: Robot-like, placeholders, or irrelevant.

Task:
1. Critique the email.
2. Assign a score (0-100).

Output JSON:
{{
  "critique": "...",
  "score": 85
}}
"""
    response = call_llm(prompt, json_mode=True)

    try:
        data = json.loads(response)
        score = int(data.get("score", 0))
        print(f"🧐 Evaluator Critique: {data.get('critique', 'No critique')}")
        return max(0, min(score, 100))
    except:
        return 0

# -------------------------------------------------
# 5. MAIN EXECUTION LOOP
# -------------------------------------------------

def run_sdr_agent():
    # Updated: Use fetch_leads_by_status("New") instead of fetch_new_leads
    leads = fetch_leads_by_status("New")

    if not leads:
        print("No new leads found.")
        return

    # Iterating over list of objects, not DataFrame rows
    for lead in leads:
        lead_id = lead.id
        name = safe_str(getattr(lead, 'name', 'Prospect'))
        
        print(f"\n🔍 Analyzing Lead: {name}...")

        # ----------------------------------------
        # GATE 1: Negative Signal Check
        # ----------------------------------------
        is_blocked, block_reason = check_negative_gate(lead)
        if is_blocked:
            print(f"⛔ BLOCKED: {block_reason}")
            update_lead_status(lead_id, f"Skipped: {block_reason}")
            mark_review_decision(lead_id, "BLOCKED")
            continue

        # ----------------------------------------
        # GATE 2: Signal Strength Score
        # ----------------------------------------
        signal_score, reasons = calculate_signal_score(lead)
        update_lead_signal_score(lead_id, signal_score)
        print(f"📊 Signal Score: {signal_score}/100")
        if reasons:
            print(f"   Matches: {', '.join(reasons)}")

        if signal_score < SIGNAL_THRESHOLD:
            print(f"📉 Low Signal (<{SIGNAL_THRESHOLD}) - Skipping Generation")
            update_lead_status(lead_id, f"Skipped: Low Signal ({signal_score})")
            mark_review_decision(lead_id, "SKIPPED")
            continue

        # ----------------------------------------
        # GENERATION (Costly Step)
        # ----------------------------------------
        print("✅ Gates Passed. Generating Email...")
        
        body = generate_email_body(lead)
        if not body:
            print("❌ Generation failed (empty body).")
            continue
            
        final_email = inject_signature(body)

        # ----------------------------------------
        # VALIDATION & SCORING
        # ----------------------------------------
        if not validate_structure(final_email):
            print("❌ Structural validation failed.")
            save_draft(lead_id, final_email, 0, "STRUCTURAL_FAILED")
            continue

        score = evaluate_email(final_email)
        print(f"📝 Final Score: {score}")

        status = "Approved" if score >= APPROVAL_THRESHOLD else "Pending"
        save_draft(lead_id, final_email, score, status)

        if status == "Approved":
            print("🚀 Auto-Approved!")
            update_lead_status(lead_id, "Contacted")
        else:
            print("⚠️ Sent for Human Review.")

if __name__ == "__main__":
    run_sdr_agent()
