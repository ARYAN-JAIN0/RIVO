import pandas as pd
from pathlib import Path
from datetime import datetime

DEALS_FILE = Path("db/deals.csv")

if not DEALS_FILE.exists() or DEALS_FILE.stat().st_size == 0:
    df = pd.DataFrame(columns=[
        "deal_id",
        "lead_id",
        "company",
        "amount",
        "stage",
        "confidence_score",
        "notes",
        "created_at"
    ])
else:
    df = pd.read_csv(DEALS_FILE)

df["deal_id"] = pd.to_numeric(df.get("deal_id", 0), errors="coerce").fillna(0).astype(int)
df["lead_id"] = pd.to_numeric(df.get("lead_id", 0), errors="coerce").fillna(0).astype(int)
df["amount"] = pd.to_numeric(df.get("amount", 0.0), errors="coerce").fillna(0.0)
df["confidence_score"] = pd.to_numeric(df.get("confidence_score", 0.0), errors="coerce").fillna(0.0)

df["company"] = df.get("company", "").astype(str)
df["stage"] = df.get("stage", "Qualified").astype(str)
df["notes"] = df.get("notes", "").astype(str)
df["created_at"] = df.get("created_at", datetime.now().strftime("%Y-%m-%d")).astype(str)

df.to_csv(DEALS_FILE, index=False)

print("✅ Deals schema repaired successfully")
