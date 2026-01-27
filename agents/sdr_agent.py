# agents/sdr_agent.py
import json
import re
from RIVO.db.db_handler import (
    fetch_new_leads,
    update_lead_status,
    save_draft
)
from RIVO.services.llm_client import call_llm
from RIVO.config.sdr_profile import (
    SDR_NAME,
    SDR_COMPANY,
    SDR_ROLE,
    SDR_EMAIL
)

APPROVAL_THRESHOLD = 85  # Kept high to ensure quality

# -------------------------------------------------
# 1. FIXED STRUCTURAL VALIDATION
# -------------------------------------------------

def validate_structure(email_text: str) -> bool:
    if not email_text or not isinstance(email_text, str):
        return False

    text = email_text.lower().strip()

    # Tokens strictly forbidden (Placeholders that shouldn't be there)
    forbidden_tokens = [
        "[your name]", "[your company]", "[insert", "{name}", "{company}"
    ]
    for token in forbidden_tokens:
        if token in text:
            return False

    # FIX: Smarter Signoff Check
    # Instead of counting overlaps, we check if the email ends with the correct signature block.
    # The injection adds SDR_EMAIL at the very end.
    if not text.endswith(SDR_EMAIL.lower()):
        return False
        
    # FIX: Adjusted Word Count
    # Lowered minimum to 30 to allow concise, punchy emails.
    word_count = len(text.split())
    if word_count < 30 or word_count > 150: 
        return False

    return True


# -------------------------------------------------
# 2. CHAIN-OF-THOUGHT GENERATION (Higher Quality)
# -------------------------------------------------

def generate_email_body(lead):
    name = lead.get('name', 'Prospect')
    company = lead.get('company', 'your company')
    industry = lead.get('industry', 'your industry')
    insight = lead.get('verified_insight', f'recent trends in {industry}')

    # We ask for a JSON object with "thought_process" and "email_body".
    # This forces the model to PLAN the personalization before WRITING it.
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
    response_text = call_llm(prompt, json_mode=True).strip()
    
    try:
        data = json.loads(response_text)
        return data.get("email_body", "")
    except json.JSONDecodeError:
        # Fallback: try to find the email in the raw text if JSON fails
        return response_text


def inject_signature(body: str) -> str:
    # Ensure we don't double-inject if the model ignored instructions
    clean_body = body.replace("[Signature]", "").strip()
    return f"""{clean_body}

Best regards,
{SDR_NAME}
{SDR_ROLE}, {SDR_COMPANY}
{SDR_EMAIL}"""


# -------------------------------------------------
# 3. ROBUST EVALUATION
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
        print(f"🧐 Evaluator Critique: {data.get('critique')}")
        return max(0, min(score, 100))
    except:
        return 0


# -------------------------------------------------
# MAIN LOOP
# -------------------------------------------------

def run_sdr_agent():
    leads = fetch_new_leads()
    if leads.empty:
        print("No new leads found.")
        return

    for _, lead in leads.iterrows():
        print(f"\nProcessing: {lead['name']}...")

        # Generate with Chain-of-Thought
        body = generate_email_body(lead)
        if not body:
            print("❌ Generation failed (empty body).")
            continue
            
        final_email = inject_signature(body)

        # Validate
        if not validate_structure(final_email):
            print("❌ Structural validation failed.")
            save_draft(lead["id"], final_email, 0, "STRUCTURAL_FAILED")
            continue

        # Evaluate
        score = evaluate_email(final_email)
        print(f"✅ Generated (Score: {score})")

        status = "Approved" if score >= APPROVAL_THRESHOLD else "Pending"
        save_draft(lead["id"], final_email, score, status)

        if status == "Approved":
            update_lead_status(lead["id"], "Contacted")

if __name__ == "__main__":
    run_sdr_agent()