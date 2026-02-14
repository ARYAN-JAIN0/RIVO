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
python app/database/init_db.py
python app/orchestrator.py
```

## Run Modes

```bash
python app/orchestrator.py              # full pipeline
python app/orchestrator.py sdr          # single agent
python app/orchestrator.py health       # health JSON
streamlit run app/multi_agent_dashboard.py
```

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

