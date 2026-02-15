# RIVO

RIVO is a multi-agent revenue workflow system with four stages:

1. SDR (`New` leads -> pending human email review)
2. Sales (`Contacted` leads -> pending deal review)
3. Negotiation (`Proposal Sent` deals -> pending contract review)
4. Finance (`Signed` contracts -> pending dunning review)

The stack uses SQLAlchemy ORM with SQLite (default) or PostgreSQL.

## Quick Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env
python -m app.database.init_db
python app/orchestrator.py
```

## Run Modes

```bash
python app/orchestrator.py              # full pipeline
python app/orchestrator.py sdr          # single agent
python app/orchestrator.py health       # health JSON
streamlit run app/multi_agent_dashboard.py
```

If your local PostgreSQL credentials are not configured yet, you can either
switch to SQLite in `.env`:

```bash
DATABASE_URL=sqlite:///./rivo.db
```

or keep your current URL and allow startup to continue while showing DB errors:

```bash
DB_CONNECTIVITY_REQUIRED=false
```

If startup cannot connect to PostgreSQL and connectivity is optional, RIVO now
falls back to local SQLite automatically for local development.

## Full Pipeline Runbook (Repeatable)

Use this sequence whenever you want to run end-to-end from a clean local setup.

Shortcut (PowerShell, scripted flow with review gates):

```bash
.\run_full_pipeline.ps1
```

```bash
# 1) Initialize schema
python -m app.database.init_db

# 2) Seed leads (choose one)
python scripts/seed_data.py
# OR
python scripts/seed_20_leads.py

# 3) Run SDR stage (creates pending email reviews)
python app/orchestrator.py sdr

# 4) Open review dashboard and approve/reject SDR drafts
streamlit run app/multi_agent_dashboard.py

# 5) Run Sales stage (for contacted leads)
python app/orchestrator.py sales

# 6) Approve/reject pending deal reviews in dashboard
streamlit run app/multi_agent_dashboard.py

# 7) Run Negotiation stage (for proposal-sent deals)
python app/orchestrator.py negotiation

# 8) Approve/reject pending contract reviews in dashboard
streamlit run app/multi_agent_dashboard.py

# 9) Run Finance stage (for signed contracts)
python app/orchestrator.py finance

# 10) Approve/reject dunning drafts in dashboard
streamlit run app/multi_agent_dashboard.py

# 11) Verify system state
python app/orchestrator.py health
python scripts/view_all_data.py
```

Notes:

- Human review is mandatory between stages; pipeline progression is gated by approvals.
- `python app/orchestrator.py` runs all agents in order, but later stages will be no-op until review decisions move records forward.
- Repeat steps 3-11 as needed for continuous operation.

## Human Review Gate

- SDR drafts are stored as `review_status=Pending`; no auto-send.
- Deal/contract/dunning outputs are also persisted as pending review.
- Status progression to `Contacted`, `Proposal Sent`, `Signed`, and dunning advancement occurs on explicit decision functions.
- Review decisions are recorded in `review_audit`.

## Migrations (Alembic)

```bash
alembic upgrade head
```

Baseline migration lives at:

- `migrations/versions/20260213_0001_baseline_schema.py`

## Docker

`docker-compose.yml` provides:

- `db` (PostgreSQL)
- `ollama` (LLM runtime)
- `app` (orchestrator worker)
- `dashboard` (Streamlit review UI)

Start stack:

```bash
docker-compose up -d --build
```

## Testing

```bash
pytest -q
```

Current test suite focuses on critical integrity behavior:

- no status transition during draft save
- invoice deduplication
- deterministic structure validation
- orchestrator health pending-review counts
