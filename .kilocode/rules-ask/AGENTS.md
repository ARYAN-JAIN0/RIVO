# Ask Mode Rules

## Project Overview
RIVO is a multi-agent sales automation system with pipeline: SDR → Sales → Negotiation → Finance.

## Key Architecture Points
- **FastAPI backend** with endpoints in [`app/api/v1/endpoints.py`](app/api/v1/endpoints.py)
- **SQLAlchemy ORM** with models in [`app/database/models.py`](app/database/models.py)
- **Ollama LLM** integration via [`call_llm()`](app/services/llm_client.py:29)
- **Alembic migrations** in `migrations/versions/` directory
- **Celery tasks** for async agent execution in [`app/tasks/agent_tasks.py`](app/tasks/agent_tasks.py)

## Status Enums
All status values use title case: `"New"`, `"Contacted"`, `"Qualified"`, `"Proposal Sent"`, etc. See [`app/core/enums.py`](app/core/enums.py).

## Configuration
Runtime config via [`app/core/config.py`](app/core/config.py) - uses environment variables with defaults. Key settings:
- `DATABASE_URL`: PostgreSQL or SQLite connection (default: `sqlite:///./rivo.db`)
- `OLLAMA_URL`: LLM endpoint (default: `http://localhost:11434`)
- `OLLAMA_MODEL`: Model name (default: `qwen2.5:7b`)
- `DB_CONNECTIVITY_REQUIRED`: When false (default), auto-falls back to SQLite if PostgreSQL unavailable

## Data Flow
1. Leads enter via SDR agent (status: New)
2. SDR generates outreach emails, leads progress to Contacted
3. Sales agent qualifies leads, creates deals (status: Qualified)
4. Negotiation agent handles contracts (status: Negotiating → Signed)
5. Finance agent processes invoices (status: Sent → Paid/Overdue)

## Entity Lifecycle

| Entity | Status Flow |
|--------|-------------|
| Lead | New → Contacted → Qualified/Disqualified |
| Deal | Qualified → Proposal Sent → Won/Lost |
| Contract | Negotiating → Signed → Completed/Cancelled |
| Invoice | Sent → Paid/Overdue |

## Key Thresholds
- SDR `REVIEW_QUEUE_THRESHOLD`: 85 (min score for review queue)
- SDR `SIGNAL_THRESHOLD`: 60 (min signal score to proceed)
- Negotiation `MAX_NEGOTIATION_TURNS`: 3

## Documentation
- [`README.md`](README.md) for project overview
- [`db/schema.sql`](db/schema.sql) for database schema reference
- [`docs/phase1/`](docs/phase1/) for architecture documentation
