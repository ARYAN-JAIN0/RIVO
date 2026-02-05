# Database Handler (CSV-based)
# Phase-3 Extension: Preserves ALL existing Phase-2 functions unchanged

import pandas as pd
from datetime import datetime
from pathlib import Path

# Resolve project root dynamically
BASE_DIR = Path(__file__).resolve().parents[1]
LEADS_FILE = BASE_DIR / "db" / "leads.csv"

# Phase-3 Extension: New data files (existing leads.csv untouched)
DEALS_FILE = BASE_DIR / "db" / "deals.csv"
CONTRACTS_FILE = BASE_DIR / "db" / "contracts.csv"
INVOICES_FILE = BASE_DIR / "db" / "invoices.csv"


# ==============================================================================
# PHASE-2 FUNCTIONS (UNCHANGED - DO NOT MODIFY)
# ==============================================================================

def fetch_new_leads():
    df = pd.read_csv(LEADS_FILE)
    return df[df["status"] == "New"]


def update_lead_status(lead_id, new_status):
    df = pd.read_csv(LEADS_FILE)
    df.loc[df["id"] == lead_id, "status"] = new_status
    df.loc[df["id"] == lead_id, "last_contacted"] = datetime.now().strftime("%Y-%m-%d")
    df.to_csv(LEADS_FILE, index=False)


def save_draft(lead_id, email_text, score, review_status="Pending"):
    df = pd.read_csv(LEADS_FILE)
    df.loc[df["id"] == lead_id, "draft_email"] = email_text
    df.loc[df["id"] == lead_id, "confidence_score"] = score
    df.loc[df["id"] == lead_id, "review_status"] = review_status
    df.to_csv(LEADS_FILE, index=False)


def fetch_pending_reviews(include_structural_failed=False):
    df = pd.read_csv(LEADS_FILE)

    if include_structural_failed:
        return df[df["review_status"].isin(["Pending", "STRUCTURAL_FAILED"])]

    return df[df["review_status"] == "Pending"]


def mark_review_decision(lead_id, decision, edited_email=None):
    df = pd.read_csv(LEADS_FILE)

    df.loc[df["id"] == lead_id, "review_status"] = decision

    if edited_email:
        df.loc[df["id"] == lead_id, "draft_email"] = edited_email

    if decision == "Approved":
        df.loc[df["id"] == lead_id, "status"] = "Contacted"
        df.loc[df["id"] == lead_id, "last_contacted"] = datetime.now().strftime("%Y-%m-%d")
        
    df.to_csv(LEADS_FILE, index=False)


# ==============================================================================
# PHASE-3 EXTENSIONS (NEW FUNCTIONS ONLY - APPEND-ONLY STRATEGY)
# ==============================================================================

# ---------------------
# Generic Lead Queries
# ---------------------

def fetch_leads_by_status(status: str):
    """Generic status query for orchestrator health checks."""
    df = pd.read_csv(LEADS_FILE)
    return df[df["status"] == status]


# ---------------------
# DEALS (Sales Pipeline)
# ---------------------

def create_deal(lead_id, stage="Qualified", qualification_score=0, deal_value=0, notes=""):
    """Create a new deal from a contacted lead."""
    df = pd.read_csv(DEALS_FILE)
    
    new_deal_id = df["deal_id"].max() + 1 if not df.empty else 1
    
    new_deal = {
        "deal_id": new_deal_id,
        "lead_id": lead_id,
        "stage": stage,
        "qualification_score": qualification_score,
        "proposal_sent_date": "",
        "expected_close_date": "",
        "deal_value": deal_value,
        "notes": notes,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "review_status": "Pending" if qualification_score < 85 else "Auto-Approved"
    }
    
    df = pd.concat([df, pd.DataFrame([new_deal])], ignore_index=True)
    df.to_csv(DEALS_FILE, index=False)
    
    return new_deal_id


def fetch_deals_by_status(stage: str):
    """Fetch deals by pipeline stage."""
    df = pd.read_csv(DEALS_FILE)
    if df.empty:
        return df
    return df[df["stage"] == stage]


def update_deal_stage(deal_id, new_stage, notes=""):
    """Progress deal through pipeline."""
    df = pd.read_csv(DEALS_FILE)
    df.loc[df["deal_id"] == deal_id, "stage"] = new_stage
    df.loc[df["deal_id"] == deal_id, "last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if notes:
        df.loc[df["deal_id"] == deal_id, "notes"] = notes
    df.to_csv(DEALS_FILE, index=False)


def save_deal_review(deal_id, notes, score, review_status="Pending"):
    """Save deal analysis for human review."""
    df = pd.read_csv(DEALS_FILE)
    df.loc[df["deal_id"] == deal_id, "qualification_score"] = score
    df.loc[df["deal_id"] == deal_id, "notes"] = notes
    df.loc[df["deal_id"] == deal_id, "review_status"] = review_status
    df.loc[df["deal_id"] == deal_id, "last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df.to_csv(DEALS_FILE, index=False)


def fetch_pending_deal_reviews():
    """Fetch deals requiring human review."""
    df = pd.read_csv(DEALS_FILE)
    if df.empty:
        return df
    return df[df["review_status"] == "Pending"]


def mark_deal_decision(deal_id, decision):
    """Approve or reject a deal."""
    df = pd.read_csv(DEALS_FILE)
    df.loc[df["deal_id"] == deal_id, "review_status"] = decision
    
    if decision == "Approved":
        df.loc[df["deal_id"] == deal_id, "stage"] = "Proposal Sent"
    
    df.to_csv(DEALS_FILE, index=False)


# ---------------------
# CONTRACTS (Negotiation)
# ---------------------

def create_contract(deal_id, lead_id, contract_terms, contract_value):
    """Create contract from approved deal."""
    df = pd.read_csv(CONTRACTS_FILE)
    
    new_contract_id = df["contract_id"].max() + 1 if not df.empty else 1
    
    new_contract = {
        "contract_id": new_contract_id,
        "deal_id": deal_id,
        "lead_id": lead_id,
        "status": "Negotiating",
        "contract_terms": contract_terms,
        "negotiation_points": "",
        "objections": "",
        "proposed_solutions": "",
        "signed_date": "",
        "contract_value": contract_value,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "review_status": "Pending"
    }
    
    df = pd.concat([df, pd.DataFrame([new_contract])], ignore_index=True)
    df.to_csv(CONTRACTS_FILE, index=False)
    
    return new_contract_id


def fetch_contracts_by_status(status: str):
    """Fetch contracts by negotiation status."""
    df = pd.read_csv(CONTRACTS_FILE)
    if df.empty:
        return df
    return df[df["status"] == status]


def update_contract_negotiation(contract_id, objections, proposed_solutions, confidence_score):
    """Update contract with negotiation progress."""
    df = pd.read_csv(CONTRACTS_FILE)
    df.loc[df["contract_id"] == contract_id, "objections"] = objections
    df.loc[df["contract_id"] == contract_id, "proposed_solutions"] = proposed_solutions
    df.loc[df["contract_id"] == contract_id, "last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df.loc[df["contract_id"] == contract_id, "review_status"] = "Auto-Approved" if confidence_score >= 85 else "Pending"
    df.to_csv(CONTRACTS_FILE, index=False)


def mark_contract_signed(contract_id):
    """Mark contract as signed."""
    df = pd.read_csv(CONTRACTS_FILE)
    df.loc[df["contract_id"] == contract_id, "status"] = "Signed"
    df.loc[df["contract_id"] == contract_id, "signed_date"] = datetime.now().strftime("%Y-%m-%d")
    df.loc[df["contract_id"] == contract_id, "review_status"] = "Approved"
    df.to_csv(CONTRACTS_FILE, index=False)


def fetch_pending_contract_reviews():
    """Fetch contracts requiring human review."""
    df = pd.read_csv(CONTRACTS_FILE)
    if df.empty:
        return df
    return df[df["review_status"] == "Pending"]


def mark_contract_decision(contract_id, decision):
    """Approve or reject contract negotiation strategy."""
    df = pd.read_csv(CONTRACTS_FILE)
    df.loc[df["contract_id"] == contract_id, "review_status"] = decision
    
    if decision == "Approved":
        df.loc[df["contract_id"] == contract_id, "status"] = "Signed"
        df.loc[df["contract_id"] == contract_id, "signed_date"] = datetime.now().strftime("%Y-%m-%d")
    
    df.to_csv(CONTRACTS_FILE, index=False)


# ---------------------
# INVOICES (Finance/ARRE)
# ---------------------

def create_invoice(contract_id, lead_id, amount, due_date):
    """Create invoice from signed contract."""
    df = pd.read_csv(INVOICES_FILE)
    
    new_invoice_id = df["invoice_id"].max() + 1 if not df.empty else 1
    
    new_invoice = {
        "invoice_id": new_invoice_id,
        "contract_id": contract_id,
        "lead_id": lead_id,
        "amount": amount,
        "due_date": due_date,
        "status": "Sent",
        "days_overdue": 0,
        "dunning_stage": 0,
        "last_contact_date": datetime.now().strftime("%Y-%m-%d"),
        "payment_date": "",
        "draft_message": "",
        "confidence_score": 0,
        "review_status": "New"
    }
    
    df = pd.concat([df, pd.DataFrame([new_invoice])], ignore_index=True)
    df.to_csv(INVOICES_FILE, index=False)
    
    return new_invoice_id


def fetch_invoices_by_status(status: str):
    """Fetch invoices by payment status."""
    df = pd.read_csv(INVOICES_FILE)
    if df.empty:
        return df
    return df[df["status"] == status]


def update_invoice_status(invoice_id, status, days_overdue=0, dunning_stage=0):
    """Update invoice payment status."""
    df = pd.read_csv(INVOICES_FILE)
    df.loc[df["invoice_id"] == invoice_id, "status"] = status
    df.loc[df["invoice_id"] == invoice_id, "days_overdue"] = days_overdue
    df.loc[df["invoice_id"] == invoice_id, "dunning_stage"] = dunning_stage
    df.to_csv(INVOICES_FILE, index=False)


def save_dunning_draft(invoice_id, draft_message, confidence_score):
    """Save dunning email draft for review."""
    df = pd.read_csv(INVOICES_FILE)
    df.loc[df["invoice_id"] == invoice_id, "draft_message"] = draft_message
    df.loc[df["invoice_id"] == invoice_id, "confidence_score"] = confidence_score
    df.loc[df["invoice_id"] == invoice_id, "review_status"] = "Auto-Approved" if confidence_score >= 85 else "Pending"
    df.loc[df["invoice_id"] == invoice_id, "last_contact_date"] = datetime.now().strftime("%Y-%m-%d")
    df.to_csv(INVOICES_FILE, index=False)


def mark_invoice_paid(invoice_id):
    """Mark invoice as paid."""
    df = pd.read_csv(INVOICES_FILE)
    df.loc[df["invoice_id"] == invoice_id, "status"] = "Paid"
    df.loc[df["invoice_id"] == invoice_id, "payment_date"] = datetime.now().strftime("%Y-%m-%d")
    df.to_csv(INVOICES_FILE, index=False)


def fetch_pending_dunning_reviews():
    """Fetch dunning messages requiring human review."""
    df = pd.read_csv(INVOICES_FILE)
    if df.empty:
        return df
    return df[df["review_status"] == "Pending"]


def mark_dunning_decision(invoice_id, decision):
    """Approve or reject dunning message."""
    df = pd.read_csv(INVOICES_FILE)
    df.loc[df["invoice_id"] == invoice_id, "review_status"] = decision
    
    if decision == "Approved":
        # Increment dunning stage
        current_stage = df.loc[df["invoice_id"] == invoice_id, "dunning_stage"].values[0]
        df.loc[df["invoice_id"] == invoice_id, "dunning_stage"] = current_stage + 1
        df.loc[df["invoice_id"] == invoice_id, "last_contact_date"] = datetime.now().strftime("%Y-%m-%d")
    
    df.to_csv(INVOICES_FILE, index=False)