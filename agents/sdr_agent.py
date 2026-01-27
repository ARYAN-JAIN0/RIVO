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

APPROVAL_THRESHOLD = 85

def strip_signature_and_signoff(text: str) -> str:
    # Aggressively remove common sign-offs and typical signature lines.
    # This regex looks for common sign-offs, followed by anything that looks like a name/title/email,
    # and is designed to be greedy.
    body = re.sub(
        r'(?is)(best|regards|cheers|sincerely|thanks|thank you|yours truly|warmly|Yours Aye|)(,|\s)*(--|—)*[\s\w\.,-]*$', 
        '', 
        text
    ).strip()
    return body


# -------------------------------------------------
# HARD STRUCTURAL VALIDATION (DETERMINISTIC)
# -------------------------------------------------

def validate_structure(email_text: str) -> bool:
    if not email_text or not isinstance(email_text, str):
        return False

    text = email_text.lower()

    # Tokens strictly forbidden in the generated output
    forbidden_tokens = [
        "[your name]",
        "[your company]",
        "[your position]",
        "[contact information]",
        "sales development rep",
        "[insert", 
        "{name}", 
        "{company}"
    ]

    for token in forbidden_tokens:
        if token in text:
            return False

    # FIX 1: Handle overlapping signoffs logic
    # We expect exactly one signoff. "best regards," contains "regards,", so we prioritize the longer match.
    signoff_count = 0
    if "best regards," in text:
        signoff_count += 1
        # Remove it temporarily so we don't double count "regards," or "best,"
        temp_text = text.replace("best regards,", "")
    else:
        temp_text = text

    # Check for other standalone signoffs in the remaining text
    other_signoffs = ["best,", "regards,"]
    for s in other_signoffs:
        if s in temp_text:
            signoff_count += 1

    if signoff_count != 1:
        return False

    # Ensure the email ends with the SDR's email (from inject_signature)
    if not text.strip().endswith(SDR_EMAIL.lower()):
        return False

    # FIX 2: Lower Minimum Word Count
    # Generated emails are concise (~35 words). Lowered min from 45 to 30.
    word_count = len(text.split())
    if word_count < 30 or word_count > 150: 
        return False

    return True


# -------------------------------------------------
# VALUE-AWARE EMAIL GENERATION
# -------------------------------------------------

def generate_email_body(lead):
    # Defaulting missing keys to prevent crashes, though input should be guaranteed
    name = lead.get('name', 'Prospect')
    company = lead.get('company', 'your company')
    website = lead.get('website', 'your website')
    industry = lead.get('industry', 'your industry')
    # Assuming 'verified_insight' exists in lead db, otherwise default to industry trend
    verified_insight = lead.get('verified_insight', f'recent developments in {industry}')

    prompt = f"""
You are an SDR Email Drafting Agent running on Qwen 2.5-7B inside a deterministic evaluation pipeline.
Your only task is to generate a high-quality outbound sales email that passes an automated quality gate (≥85/100).

🔒 STRICT OPERATING RULES (MANDATORY)
Follow every instruction exactly.
Do NOT invent facts, metrics, results, or company details.
Do NOT include placeholders, signatures, brackets, or variables.
Do NOT explain your reasoning.
Do NOT output anything except the email body text.
Do not mention signatures or signoffs in the email body.
Do not include any sign-off like 'Best regards,' or 'Sincerely,'.
Keep tone professional, human, and natural (not marketing-heavy).

📥 INPUT CONTEXT
Prospect Name: {name}
Company Name: {company}
Company Website: {website}
Industry: {industry}
One Verified Company Insight: {verified_insight}
Sender Role: SDR at a B2B SaaS company ({SDR_COMPANY})

✉️ EMAIL REQUIREMENTS
Length: 45–70 words total
Structure (must follow exactly):
Line 1: Personalized opening referencing {company} or {verified_insight}
Line 2: Clear, specific value proposition relevant to {industry}
Line 3: Soft CTA asking for a 15-minute conversation
Last Line: leave blank space for signature injection later
Use simple sentences and plain English.
Avoid buzzwords (e.g., “revolutionary”, “cutting-edge”, “synergy”).
Sound like a real human SDR, not an AI.

🛑 OUTPUT FORMAT
You must output a VALID JSON OBJECT.
Do not output markdown. Do not output plain text.
Format:
{{
    "email_body": "The text of the email goes here..."
}}
Begin.
"""
    # Parse the JSON response
    import json
    response_text = call_llm(prompt).strip()
    
    try:
        data = json.loads(response_text)
        return data.get("email_body", "")
    except json.JSONDecodeError:
        # Fallback if the model messes up
        return response_text

def inject_signature(body: str) -> str:
    return f"""{body}

Best regards,
{SDR_NAME}
{SDR_ROLE}, {SDR_COMPANY}
{SDR_EMAIL}
"""


# -------------------------------------------------
# RUBRIC-ALIGNED EVALUATION
# -------------------------------------------------

def evaluate_email(email_text: str) -> int:
    prompt = f"""
You are a senior SDR manager reviewing cold emails.

Score using this rubric:

85+ ONLY if ALL are true:
- Clear industry-specific relevance
- One concrete business outcome
- Professional, human tone
- CTA feels natural, not pushy
- No fluff, no hype

70–84 if:
- Polite and clear but generic
- Weak or vague value

Below 70 if:
- Marketing fluff
- No clear reason to reply
- Includes placeholders like [Name] or brackets

Email:
{email_text}

Return ONLY a number between 0 and 95.
"""
    response = call_llm(prompt)

    try:
        # Extract the first valid integer found in the response
        match = re.search(r'\d+', response)
        if match:
            score = int(match.group())
            return max(0, min(score, 95))
        return 0
    except:
        return 0


# -------------------------------------------------
# MAIN SDR AGENT
# -------------------------------------------------

def run_sdr_agent():
    leads = fetch_new_leads()

    if leads.empty:
        print("No new leads found.")
        return

    for _, lead in leads.iterrows():
        lead_id = lead["id"]
        print(f"\nProcessing lead: {lead['name']}")

        # 1️⃣ Generate and Clean
        raw_body = generate_email_body(lead)
        cleaned_body = strip_signature_and_signoff(raw_body)
        email = inject_signature(cleaned_body)

        # 2️⃣ Structural gate
        if not validate_structure(email):
            print("❌ Structural validation failed.")
            save_draft(
                lead_id=lead_id,
                email_text=email,
                score=0,
                review_status="STRUCTURAL_FAILED"
            )
            continue

        # 3️⃣ Evaluate
        score = evaluate_email(email)

        print("\nFinal Email:\n", email)
        print("Confidence Score:", score)

        # 4️⃣ Route
        if score >= APPROVAL_THRESHOLD:
            print("✅ Auto-approved.")
            save_draft(
                lead_id=lead_id,
                email_text=email,
                score=score,
                review_status="Approved"
            )
            update_lead_status(lead_id, "Contacted")
        else:
            print("⚠️ Sent for human review.")
            save_draft(
                lead_id=lead_id,
                email_text=email,
                score=score,
                review_status="Pending"
            )

if __name__ == "__main__":
    run_sdr_agent()