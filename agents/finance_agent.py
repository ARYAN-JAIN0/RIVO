# Finance Agent

"""
Finance Agent - ARRE (Accounts Receivable Recovery Engine)

PHASE-3 EXTENSION: Runs after contracts are signed.
Trigger: Contract status = "Signed"
Output: Invoices with dunning email drafts for overdue accounts

BACKWARD COMPATIBILITY:
- Reads from contracts.csv (status="Signed")
- Writes ONLY to invoices.csv
- Same pattern: analysis → generation → scoring → approval/review
"""

import json
import pandas as pd
from datetime import datetime, timedelta

from db.db_handler import (
    fetch_contracts_by_status,
    create_invoice,
    fetch_invoices_by_status,
    update_invoice_status,
    save_dunning_draft
)
from services.llm_client import call_llm
from config.sdr_profile import SDR_NAME, SDR_COMPANY, SDR_EMAIL


# Configuration
DUNNING_APPROVAL_THRESHOLD = 85
PAYMENT_TERMS_DAYS = 30  # Net-30 payment terms


# Dunning Stage Escalation Strategy
DUNNING_STAGES = {
    0: {"days": 0, "tone": "friendly_reminder", "subject": "Invoice Payment Confirmation"},
    1: {"days": 7, "tone": "polite_reminder", "subject": "Payment Due Reminder"},
    2: {"days": 14, "tone": "urgent_reminder", "subject": "Urgent: Payment Now Overdue"},
    3: {"days": 21, "tone": "final_notice", "subject": "Final Notice: Account Suspension Pending"},
    4: {"days": 30, "tone": "collections", "subject": "Account Suspended - Collections Process"}
}


def calculate_days_overdue(due_date_str: str) -> int:
    """Calculate how many days past due date."""
    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        delta = (datetime.now() - due_date).days
        return max(0, delta)  # Never negative
    except (ValueError, AttributeError):
        return 0


def determine_dunning_stage(days_overdue: int) -> int:
    """
    Determine appropriate dunning stage based on days overdue.
    Returns stage number (0-4).
    """
    if days_overdue >= 30:
        return 4  # Collections
    elif days_overdue >= 21:
        return 3  # Final notice
    elif days_overdue >= 14:
        return 2  # Urgent
    elif days_overdue >= 7:
        return 1  # Polite reminder
    else:
        return 0  # Friendly reminder


def generate_dunning_email(invoice, stage_config) -> tuple[str, int]:
    """
    Generate dunning email using LLM with appropriate tone.
    Returns (email_body, confidence_score).
    """
    company = str(invoice.get('company', 'Customer'))
    amount = invoice.get('amount', 0)
    invoice_id = invoice.get('invoice_id', 'INV-XXX')
    days_overdue = invoice.get('days_overdue', 0)
    tone = stage_config['tone']
    
    # Tone guidelines for different stages
    tone_guidelines = {
        "friendly_reminder": "Warm, helpful, assumes good intent. No urgency.",
        "polite_reminder": "Professional, gentle nudge. Offer to help with any issues.",
        "urgent_reminder": "More direct, emphasize business impact. Still professional.",
        "final_notice": "Serious but professional. Clear consequences stated.",
        "collections": "Formal, legal language. Account suspension notice."
    }
    
    prompt = f"""
You are a Finance Operations Specialist writing a dunning email.

Context:
- Customer: {company}
- Invoice: #{invoice_id}
- Amount: ${amount:,}
- Days Overdue: {days_overdue}
- Stage: {tone.replace('_', ' ').title()}

Tone Guidelines: {tone_guidelines[tone]}

Task: Write a dunning email that:
1. States the facts clearly (amount, due date, days overdue)
2. Matches the appropriate tone for this stage
3. Includes clear next steps (payment link, contact info)
4. Maintains professional relationship

DO NOT:
- Use placeholders like [Company Name] or [Amount]
- Include signature block (will be added automatically)
- Exceed 100 words (be concise)

Output JSON only:
{{
  "email_body": "The actual email text here...",
  "confidence": 85
}}

Confidence guidelines:
- 90-100: Routine follow-up, standard language
- 75-89: Sensitive situation requiring review
- Below 75: Complex customer relationship, escalate
"""
    
    try:
        response = call_llm(prompt, json_mode=True)
        data = json.loads(response)
        
        email_body = data.get('email_body', '')
        confidence = int(data.get('confidence', 0))
        
        # Add subject line
        subject = stage_config['subject']
        
        return email_body, min(max(confidence, 0), 100)
    
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️  LLM failed, using template: {e}")
        
        # Deterministic fallback templates
        templates = {
            "friendly_reminder": f"Hi there, just a friendly reminder that invoice #{invoice_id} for ${amount:,} is now due. If you've already sent payment, please disregard this message. Otherwise, you can pay via [payment link]. Let me know if you have any questions!",
            
            "polite_reminder": f"I wanted to follow up on invoice #{invoice_id} for ${amount:,}, which is now {days_overdue} days past due. If there are any issues preventing payment, I'm happy to help resolve them. Please let me know how we can assist.",
            
            "urgent_reminder": f"Our records show invoice #{invoice_id} for ${amount:,} is now {days_overdue} days overdue. To avoid any service interruptions, please process payment immediately. If you have questions about the invoice, please contact us within 48 hours.",
            
            "final_notice": f"This is a final notice regarding invoice #{invoice_id} for ${amount:,}, now {days_overdue} days overdue. Failure to pay within 7 days will result in account suspension and potential collections action. Please remit payment immediately or contact us to arrange a payment plan.",
            
            "collections": f"Your account has been suspended due to non-payment of invoice #{invoice_id} (${amount:,}, {days_overdue} days overdue). This matter has been escalated to our collections department. To restore service and avoid further action, immediate payment is required. Contact our finance team at {SDR_EMAIL}."
        }
        
        return templates.get(tone, templates["polite_reminder"]), 70


def inject_dunning_signature(body: str, invoice_id: int) -> str:
    """Add signature and payment instructions to dunning email."""
    return f"""{body}

Payment Options:
- Online: [Payment Portal Link]
- Wire Transfer: [Banking Details]
- Check: [Mailing Address]

Reference: Invoice #{invoice_id}

Best regards,
{SDR_NAME}
{SDR_COMPANY} Finance Team
{SDR_EMAIL}
"""


def run_finance_agent():
    """
    Main Finance Agent execution loop.
    
    Process:
    1. Check all invoices for overdue status
    2. Calculate days overdue
    3. Determine appropriate dunning stage
    4. Generate dunning email with appropriate tone
    5. Score confidence
    6. Auto-approve (≥85) or send for human review
    """
    # First, create invoices for newly signed contracts
    print(f"\n{'='*60}")
    print(f"💰 FINANCE AGENT: Invoice & Dunning Management")
    print(f"{'='*60}\n")
    
    print("📋 Step 1: Creating invoices for signed contracts...")
    signed_contracts = fetch_contracts_by_status("Signed")
    
    if not signed_contracts.empty:
        for _, contract in signed_contracts.iterrows():
            contract_id = contract["contract_id"]
            lead_id = contract["lead_id"]
            amount = contract.get("contract_value", 0)
            
            # Set due date to 30 days from signed date
            signed_date_str = contract.get("signed_date", datetime.now().strftime("%Y-%m-%d"))
            try:
                signed_date = datetime.strptime(signed_date_str, "%Y-%m-%d")
                due_date = signed_date + timedelta(days=PAYMENT_TERMS_DAYS)
            except:
                due_date = datetime.now() + timedelta(days=PAYMENT_TERMS_DAYS)
            
            # Check if invoice already exists
            # (In production, would query invoices by contract_id)
            
            invoice_id = create_invoice(
                contract_id=contract_id,
                lead_id=lead_id,
                amount=amount,
                due_date=due_date.strftime("%Y-%m-%d")
            )
            
            print(f"   ✅ Invoice #{invoice_id} created: ${amount:,} due {due_date.strftime('%Y-%m-%d')}")
    else:
        print("   No new signed contracts to invoice.")
    
    # Now process overdue invoices
    print(f"\n📋 Step 2: Processing overdue invoices...")
    
    # Fetch all sent invoices (could be paid, sent, or overdue)
    all_invoices = pd.read_csv(BASE_DIR / "db" / "invoices.csv") if (BASE_DIR / "db" / "invoices.csv").exists() else pd.DataFrame()
    
    if all_invoices.empty:
        print("   No invoices to process.")
        return
    
    # Filter for unpaid invoices only
    unpaid = all_invoices[all_invoices['status'].isin(['Sent', 'Overdue'])]
    
    if unpaid.empty:
        print("   All invoices are paid!")
        return
    
    print(f"   Found {len(unpaid)} unpaid invoices\n")
    
    for _, invoice in unpaid.iterrows():
        invoice_id = invoice['invoice_id']
        due_date = invoice['due_date']
        amount = invoice['amount']
        current_stage = invoice.get('dunning_stage', 0)
        
        # Calculate days overdue
        days_overdue = calculate_days_overdue(due_date)
        
        if days_overdue == 0:
            print(f"💚 Invoice #{invoice_id}: Not yet due")
            continue
        
        # Determine appropriate dunning stage
        target_stage = determine_dunning_stage(days_overdue)
        
        # Only send dunning email if we're escalating to new stage
        if target_stage <= current_stage:
            print(f"📧 Invoice #{invoice_id}: Already contacted at stage {current_stage}")
            continue
        
        print(f"\n⚠️  Invoice #{invoice_id}: ${amount:,} - {days_overdue} days overdue")
        print(f"   Escalating from stage {current_stage} → {target_stage}")
        
        # Get stage configuration
        stage_config = DUNNING_STAGES[target_stage]
        
        # Generate dunning email
        print(f"   📝 Generating {stage_config['tone'].replace('_', ' ')} email...")
        email_body, confidence = generate_dunning_email(invoice, stage_config)
        
        # Add signature
        final_email = inject_dunning_signature(email_body, invoice_id)
        
        print(f"   📊 Confidence: {confidence}/100")
        
        # Update invoice status
        update_invoice_status(
            invoice_id=invoice_id,
            status="Overdue",
            days_overdue=days_overdue,
            dunning_stage=target_stage
        )
        
        # Save draft for review
        save_dunning_draft(
            invoice_id=invoice_id,
            draft_message=final_email,
            confidence_score=confidence
        )
        
        if confidence >= DUNNING_APPROVAL_THRESHOLD:
            print(f"   ✅ Auto-Approved - Ready to send")
        else:
            print(f"   ⚠️  Pending Review - Sensitive customer relationship")
    
    print(f"\n{'='*60}")
    print("💰 Finance Agent completed")
    print(f"{'='*60}\n")


# Import BASE_DIR from db_handler
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    run_finance_agent()