# Database Handler (CSV-based)
# Phase-3 Extension: Preserves ALL existing Phase-2 functions unchanged

import pandas as pd
from datetime import datetime
from pathlib import Path
import os

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

    # Auto-heal missing status column
    if "status" not in df.columns:
        df["status"] = "New"

    df.to_csv(LEADS_FILE, index=False)
    return df[df["status"] == "New"]



def update_lead_status(lead_id, status):
    df = pd.read_csv(LEADS_FILE)

    # Ensure column exists
    if "last_contacted" not in df.columns:
        df["last_contacted"] = ""

    # Force correct dtype (critical fix)
    df["last_contacted"] = df["last_contacted"].astype(str)

    df.loc[df["id"] == lead_id, "status"] = status
    df.loc[df["id"] == lead_id, "last_contacted"] = datetime.now().strftime("%Y-%m-%d")

    df.to_csv(LEADS_FILE, index=False)


def save_draft(lead_id, draft_message, score, status):
    df = pd.read_csv(LEADS_FILE)

    # ---------- HARD SCHEMA ENFORCEMENT ----------
    REQUIRED_COLUMNS = {
        "status": "New",
        "draft_message": "",
        "confidence_score": 0.0,
        "review_status": "New"
    }

    for col, default in REQUIRED_COLUMNS.items():
        if col not in df.columns:
            df[col] = default

    # FORCE correct dtypes (this is the critical fix)
    df["status"] = df["status"].astype(str)
    df["draft_message"] = df["draft_message"].astype(str)
    df["review_status"] = df["review_status"].astype(str)
    df["confidence_score"] = pd.to_numeric(df["confidence_score"], errors="coerce").fillna(0.0)

    # ---------- SAFE WRITES ----------
    df.loc[df["id"] == lead_id, "draft_message"] = str(draft_message)
    df.loc[df["id"] == lead_id, "confidence_score"] = float(score)
    df.loc[df["id"] == lead_id, "review_status"] = str(status)
    df.loc[df["id"] == lead_id, "status"] = "Contacted"

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
        df.loc[df["id"] == lead_id, "draft_message"] = edited_email 

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
    df = pd.read_csv(LEADS_FILE)

    # Auto-heal missing status column
    if "status" not in df.columns:
        df["status"] = "New"

    df.to_csv(LEADS_FILE, index=False)
    return df[df["status"] == status]



# ---------------------
# DEALS (Sales Pipeline)
# ---------------------

def create_deal(
    lead_id,
    company=None,
    acv=None,
    deal_value=None,
    qualification_score=None,
    notes="",
    stage="qualified"
):
    import pandas as pd
    from datetime import datetime

    # --------- SAFETY CHECKS ----------
    if company is None:
        raise ValueError("create_deal(): 'company' is required")

    # Normalize ACV naming (support both)
    if acv is None and deal_value is not None:
        acv = deal_value

    # --------- FILE INIT ----------
    if not DEALS_FILE.exists():
        df = pd.DataFrame(columns=[
            "deal_id",
            "lead_id",
            "company",
            "acv",
            "qualification_score",
            "stage",
            "created_at",
            "notes"
        ])
    else:
        df = pd.read_csv(DEALS_FILE)

    # --------- CREATE DEAL ----------
    deal_id = f"DEAL-{len(df) + 1}"

    new_row = {
        "deal_id": deal_id,
        "lead_id": lead_id,
        "company": company,
        "acv": acv,
        "qualification_score": qualification_score,
        "stage": stage,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "notes": notes
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(DEALS_FILE, index=False)

    return deal_id




def fetch_deals_by_status(status):
    # File does not exist yet → no deals
    if not DEALS_FILE.exists():
        return pd.DataFrame()

    # File exists but empty
    if os.path.getsize(DEALS_FILE) == 0:
        return pd.DataFrame()

    df = pd.read_csv(DEALS_FILE)

    if df.empty or "stage" not in df.columns:
        return pd.DataFrame()

    return df[df["stage"] == status]


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
    # Guard against missing file
    if not DEALS_FILE.exists() or DEALS_FILE.stat().st_size == 0:
        return pd.DataFrame()
    
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
    # Initialize with schema if file missing/empty
    if not CONTRACTS_FILE.exists() or CONTRACTS_FILE.stat().st_size == 0:
        df = pd.DataFrame(columns=[
            "contract_id", "deal_id", "lead_id", "status", "contract_terms",
            "negotiation_points", "objections", "proposed_solutions",
            "signed_date", "contract_value", "last_updated", "review_status"
        ])
    else:
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


def fetch_contracts_by_status(status):
    """
    Fetch contracts filtered by status from contracts.csv
    """

    if not os.path.exists(CONTRACTS_FILE) or os.path.getsize(CONTRACTS_FILE) == 0:
        return pd.DataFrame()

    df = pd.read_csv(CONTRACTS_FILE, dtype=str)

    if "status" not in df.columns:
        return pd.DataFrame()

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
    # Guard against missing/empty file
    if not CONTRACTS_FILE.exists() or CONTRACTS_FILE.stat().st_size == 0:
        return pd.DataFrame()
    
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
from datetime import datetime
import pandas as pd

def _load_invoices_df():
    if not INVOICES_FILE.exists() or INVOICES_FILE.stat().st_size == 0:
        return pd.DataFrame(columns=[
            "invoice_id",
            "contract_id",
            "lead_id",
            "amount",
            "due_date",
            "status",
            "days_overdue",
            "dunning_stage",
            "last_contact_date",
            "payment_date",
            "draft_message",
            "confidence_score",
            "review_status"
        ])
    return pd.read_csv(INVOICES_FILE)


def create_invoice(contract_id, lead_id, amount, due_date):
    df = _load_invoices_df()

    new_invoice_id = int(df["invoice_id"].max() + 1) if not df.empty else 1

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
        "confidence_score": "",
        "review_status": "New"
    }

    df = pd.concat([df, pd.DataFrame([new_invoice])], ignore_index=True)
    df.to_csv(INVOICES_FILE, index=False)

    return new_invoice_id


def fetch_invoices_by_status(status):
    df = _load_invoices_df()
    return df[df["status"] == status]


def update_invoice_status(invoice_id, status, days_overdue=0, dunning_stage=0):
    df = _load_invoices_df()
    df.loc[df["invoice_id"] == invoice_id, ["status", "days_overdue", "dunning_stage"]] = [
        status, days_overdue, dunning_stage
    ]
    df.to_csv(INVOICES_FILE, index=False)


def save_dunning_draft(invoice_id, draft_message, confidence_score):
    df = _load_invoices_df()

    df.loc[df["invoice_id"] == invoice_id, "draft_message"] = str(draft_message)
    df.loc[df["invoice_id"] == invoice_id, "confidence_score"] = str(confidence_score)
    df.loc[df["invoice_id"] == invoice_id, "review_status"] = (
        "Auto-Approved" if confidence_score >= 85 else "Pending"
    )
    df.loc[df["invoice_id"] == invoice_id, "last_contact_date"] = datetime.now().strftime("%Y-%m-%d")

    df.to_csv(INVOICES_FILE, index=False)


def mark_invoice_paid(invoice_id):
    df = _load_invoices_df()
    df.loc[df["invoice_id"] == invoice_id, ["status", "payment_date"]] = [
        "Paid", datetime.now().strftime("%Y-%m-%d")
    ]
    df.to_csv(INVOICES_FILE, index=False)


def fetch_pending_dunning_reviews():
    df = _load_invoices_df()
    return df[df["review_status"] == "Pending"]


def mark_dunning_decision(invoice_id, decision):
    df = _load_invoices_df()
    df.loc[df["invoice_id"] == invoice_id, "review_status"] = decision

    if decision == "Approved":
        df.loc[df["invoice_id"] == invoice_id, "dunning_stage"] += 1
        df.loc[df["invoice_id"] == invoice_id, "last_contact_date"] = datetime.now().strftime("%Y-%m-%d")

    df.to_csv(INVOICES_FILE, index=False)

