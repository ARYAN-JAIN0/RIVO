# PROJECT OVERVIEW

## Simple Explanation
RIVO (Revenue Lifecycle Autopilot) is a backend system that moves B2B opportunities through a revenue workflow with human control points.

At a high level:
1. New leads are acquired.
2. SDR logic drafts outreach.
3. Sales logic qualifies and scores deals.
4. Negotiation logic prepares objection-handling strategy.
5. Finance logic creates invoices and dunning drafts.

RIVO is built for teams that want automation speed without losing approval control. Drafts and recommendations are generated automatically, but key stage changes are gated by explicit review decisions.

## Technical Explanation

### Purpose and Problem
RIVO implements a multi-stage lead-to-cash pipeline where state transitions are explicit and auditable.
- Orchestrator entrypoint: `app/orchestrator.py:34`
- API runtime entrypoint: `app/main.py:18`
- Scheduled automation entrypoint: `app/tasks/scheduler.py:193`

The system solves three technical problems:
1. Reliable stage progression across `Lead -> Deal -> Contract -> Invoice`.
2. Hybrid deterministic + LLM generation with fallback behavior.
3. Tenant-scoped operational visibility and manual override paths.

### Runtime Pipeline (Trigger to Completion)
Primary runtime sequence (code-wired):
1. Trigger:
   - API trigger: `POST /api/v1/pipeline/run` in `app/api/v1/endpoints.py:80`
   - Scheduler trigger: `automated_pipeline_run_task()` in `app/tasks/scheduler.py:193`
2. Lead acquisition:
   - API direct acquisition: `run_lead_acquisition()` in `app/api/v1/endpoints.py:65`
   - Scheduler acquisition service: `LeadScraperService.acquire_and_persist()` in `app/services/lead_scraper_service.py:760`
3. SDR processing:
   - `run_sdr_agent()` in `app/agents/sdr_agent.py:215`
4. Sales processing:
   - `run_sales_agent()` in `app/agents/sales_agent.py:21`
5. Negotiation processing:
   - `run_negotiation_agent()` in `app/agents/negotiation_agent.py:218`
6. Finance processing:
   - `run_finance_agent()` in `app/agents/finance_agent.py:148`

### Architecture Snapshot
- API layer (mounted): `app/api/v1/router.py:9` includes `endpoints` + `auth`.
- Service layer: business logic under `app/services/`.
- Agent layer: stage processors under `app/agents/`.
- Task layer: async/scheduled execution under `app/tasks/`.
- Database layer: SQLAlchemy models and data handlers under `app/database/`.

### Technology Stack (from code)
- FastAPI-compatible API wrappers: `app/api/_compat.py`
- SQLAlchemy ORM: `app/database/models.py:24`
- Celery with local fallback: `app/tasks/celery_app.py`
- JWT + RBAC authz: `app/auth/jwt.py:42`, `app/auth/rbac.py:74`
- Ollama text generation client: `app/services/llm_client.py:29`
- RAG service with embedding fallback: `app/services/rag_service.py:279`
- Streamlit dashboards (operational UI): `app/multi_agent_dashboard.py`, `app/crm_dashboard.py`

### How Major Components Connect
1. HTTP requests hit mounted routes in `app/api/v1/endpoints.py`.
2. Endpoints call services, queue tasks, or direct orchestrator methods.
3. Tasks call registered agent executors via `execute_registered_task()` (`app/tasks/agent_tasks.py:44`).
4. Agents call deterministic scoring/validation and optional LLM generation.
5. Persistence and state transitions occur through `app/database/db_handler.py` and model tables in `app/database/models.py`.

### Source-of-Truth Note
`plans/RIVO_RUNTIME_PIPELINE_ANALYSIS_REPORT.md` is useful context, but this PROJECT BIBLE resolves behavior from executable code paths first and uses that report only where it matches current implementation.
