import pandas as pd

LEADS_FILE = "db/leads.csv"

df = pd.read_csv(LEADS_FILE)

# ----- STATUS -----
if "status" not in df.columns:
    df["status"] = "New"
df["status"] = df["status"].astype(str)

# ----- DRAFT MESSAGE -----
if "draft_message" not in df.columns:
    df["draft_message"] = ""
df["draft_message"] = df["draft_message"].astype(str)

# ----- REVIEW STATUS -----
if "review_status" not in df.columns:
    df["review_status"] = "New"
df["review_status"] = df["review_status"].astype(str)

# ----- CONFIDENCE SCORE -----
if "confidence_score" not in df.columns:
    df["confidence_score"] = 0.0
df["confidence_score"] = (
    pd.to_numeric(df["confidence_score"], errors="coerce")
    .fillna(0.0)
)

df.to_csv(LEADS_FILE, index=False)

print("✅ Leads schema repaired successfully")
