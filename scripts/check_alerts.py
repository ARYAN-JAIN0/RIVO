import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text
from app.database.db import engine

LOG_PATH = Path("rivo.log")
TAIL_LINES = 5000

DB_ERR_THRESHOLD = 3
LLM_ERR_THRESHOLD = 5
PENDING_THRESHOLD = 20

tail = []
if LOG_PATH.exists():
    tail = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()[-TAIL_LINES:]

db_err = sum('"event": "database.connection_failed"' in line for line in tail)
llm_err = sum('"event": "llm.call.unavailable"' in line for line in tail)

with engine.connect() as conn:
    pending = conn.execute(text("SELECT COUNT(*) FROM leads WHERE review_status = 'Pending'")).scalar_one()

alerts = []
if db_err >= DB_ERR_THRESHOLD:
    alerts.append(f"database.connection_failed count={db_err}")
if llm_err >= LLM_ERR_THRESHOLD:
    alerts.append(f"llm.call.unavailable count={llm_err}")
if int(pending) >= PENDING_THRESHOLD:
    alerts.append(f"pending_review={pending}")

if alerts:
    print("ALERT:", " | ".join(alerts))
    raise SystemExit(2)

print(f"OK: db_err={db_err}, llm_err={llm_err}, pending={pending}")
