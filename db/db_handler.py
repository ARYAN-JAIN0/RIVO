# Database Handler (CSV-based)

import pandas as pd
from datetime import datetime
from pathlib import Path

# Resolve project root dynamically
BASE_DIR = Path(__file__).resolve().parents[1]
LEADS_FILE = BASE_DIR / "db" / "leads.csv"


# ---------------------------
# LEAD INGESTION
# ---------------------------

def fetch_new_leads():
    df = pd.read_csv(LEADS_FILE)
    return df[df["status"] == "New"]


def update_lead_status(lead_id, new_status):
    df = pd.read_csv(LEADS_FILE)
    df.loc[df["id"] == lead_id, "status"] = new_status
    df.loc[df["id"] == lead_id, "last_contacted"] = datetime.now()
    df.to_csv(LEADS_FILE, index=False)


# ---------------------------
# DRAFT STORAGE
# ---------------------------

def save_draft(lead_id, email_text, score, review_status="Pending"):
    df = pd.read_csv(LEADS_FILE)
    df.loc[df["id"] == lead_id, "draft_email"] = email_text
    df.loc[df["id"] == lead_id, "confidence_score"] = score
    df.loc[df["id"] == lead_id, "review_status"] = review_status
    df.to_csv(LEADS_FILE, index=False)


# ---------------------------
# HUMAN REVIEW
# ---------------------------

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
        df.loc[df["id"] == lead_id, "last_contacted"] = datetime.now()
        
    df.to_csv(LEADS_FILE, index=False)
