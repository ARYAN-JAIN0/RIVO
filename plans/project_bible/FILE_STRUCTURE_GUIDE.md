# FILE STRUCTURE GUIDE

## Simple Explanation
This guide maps the runtime-important folders and files so you can quickly locate where behavior lives:
- `app/database/` holds schema and transactional state helpers.
- `app/api/v1/` holds HTTP endpoints and auth routes.
- `app/services/` holds business logic and integrations.
- `plans/` holds design/audit docs used during development.

## Technical Explanation

## 1) `app/database/`

### `app/database/db.py`
- Purpose: engine/session lifecycle and DB fallback handling.
- Role: authoritative session provider for handlers/services.
- Key connections:
  - consumed by most data-access code via `get_db_session()` (`app/database/db.py:73`)
  - startup checks via `verify_database_connection()` (`app/database/db.py:82`)

### `app/database/models.py`
- Purpose: SQLAlchemy ORM definitions for runtime tables.
- Role: source model layer for leads, deals, contracts, invoices, logs, tenants/users.
- Key connections:
  - queried by endpoint handlers (`app/api/v1/endpoints.py`)
  - queried/updated by services and handlers under `app/services/` and `app/database/db_handler.py`

### `app/database/db_handler.py`
- Purpose: transactional helper functions for stage-specific state operations.
- Role: primary transition authority (review decisions, draft persistence, contract/invoice create/update).
- Key connections:
  - called directly by agents (`app/agents/sdr_agent.py:13`, `app/agents/finance_agent.py:14`)
  - called by review service facade (`app/services/review_service.py:20`)

### `app/database/init_db.py`
- Purpose: startup migration/bootstrap helper.
- Role: apply Alembic head + optional SQLite reset path for schema mismatch.
- Key connections:
  - invoked manually/scripts for environment initialization.

## 2) `app/api/v1/`

### Mounted route modules (runtime-wired)

#### `app/api/v1/endpoints.py`
- Purpose: primary operational API (agent runs, analytics, CRM actions, tracking).
- Role: main mounted route surface.
- Connected by: `app/api/v1/router.py:10`.

#### `app/api/v1/auth.py`
- Purpose: JWT login/refresh endpoints.
- Role: mounted auth route surface.
- Connected by: `app/api/v1/router.py:11`.

#### `app/api/v1/router.py`
- Purpose: compose v1 API router and include mounted modules.
- Role: binding point for `app/main.py`.

#### `app/api/v1/_authz.py`
- Purpose: bearer extraction, current user resolution, scope enforcement adapter.
- Role: shared authz helper imported by mounted endpoints.

### Present but not mounted in current runtime router
- `app/api/v1/agents.py`
- `app/api/v1/runs.py`
- `app/api/v1/reviews.py`
- `app/api/v1/prompts.py`
- `app/api/v1/health.py`

These files define valid route handlers but are not included by `app/api/v1/router.py:10-11` in current runtime mounting.

## 3) `app/services/`

### Pipeline and acquisition services
- `app/services/lead_acquisition_service.py`
  - simple public-source acquisition used by mounted `/lead-acquisition` endpoint.
- `app/services/lead_scraper_service.py`
  - production-hardened scrape/validate/persist service used by scheduler tasks.

### Revenue and stage services
- `app/services/sales_intelligence_service.py`
  - creates/updates deals, applies scoring, transitions stage, generates proposals.
- `app/services/opportunity_scoring_service.py`
  - hybrid rule + LLM probability scoring and explanation generation.
- `app/services/crm_service.py`
  - paginated tenant-scoped reads and safe CRM mutations.

### AI and retrieval services
- `app/services/llm_client.py`
  - Ollama generation wrapper; returns empty string on failure.
- `app/services/rag_service.py`
  - knowledge ingestion and semantic retrieval with embedding fallback.

### Review and messaging services
- `app/services/review_service.py`
  - facade over review decision persistence.
- `app/services/email_service.py`
  - sandbox/SMTP send paths plus email log writes.

## 4) `plans/`

### `plans/RIVO_RUNTIME_PIPELINE_ANALYSIS_REPORT.md`
- Purpose: prior deep pipeline analysis snapshot.
- Role in this documentation system: supporting reference only when it matches code.

### `plans/RIC_REPOSITORY_INTELLIGENCE_COMPILATION.md`
- Purpose: repository-wide static intelligence and risk inventory.
- Role: context and cross-check input for file-level mapping.

### `plans/project_bible/` (new)
- Purpose: consolidated, code-accurate PROJECT BIBLE documentation set.
- Role: onboarding, maintenance, extension, and runtime comprehension.

## Runtime File Dependency Path (condensed)
`app/main.py -> app/api/v1/router.py -> app/api/v1/endpoints.py -> app/services/* + app/tasks/* + app/orchestrator.py -> app/agents/* -> app/database/db_handler.py + app/database/models.py`
