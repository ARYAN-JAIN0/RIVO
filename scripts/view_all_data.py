import sys
from pathlib import Path
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app.database.db as db_module
from app.core.startup import bootstrap

def view_data():
    bootstrap()
    active_url = db_module.get_active_database_url()
    print(f"Connecting to: {active_url}")
    engine = db_module.get_engine()
    
    print("\n" + "="*50)
    print("LEADS DATA")
    print("="*50)
    try:
        leads = pd.read_sql("SELECT id, name, company, role, status, review_status, signal_score FROM leads", engine)
        if leads.empty:
             print("No leads found in the database.")
        else:
             print(f"Found {len(leads)} leads:\n")
             print(leads.to_string(index=False))
    except Exception as e:
        print(f"Error fetching leads: {e}")

    print("\n" + "="*50)
    print("DEALS DATA")
    print("="*50)
    try:
        deals = pd.read_sql("SELECT id, company, acv, qualification_score, stage, review_status FROM deals", engine)
        if deals.empty:
             print("No deals found (Sales agent might not have run yet).")
        else:
             print(f"Found {len(deals)} deals:\n")
             print(deals.to_string(index=False))
    except Exception as e:
        print(f"Error fetching deals: {e}")
        
    print("\n" + "="*50)

if __name__ == "__main__":
    view_data()
