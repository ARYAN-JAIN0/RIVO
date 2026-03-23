# SYSTEM ARCHITECTURE

## 4. System Architecture

### Simple Explanation
RIVO is a pipeline controller with four worker stages and a shared database.
API endpoints accept commands and queries, services and agents implement behavior, and the database stores truth and review decisions.
Scheduler and Celery run the same pipeline automatically when enabled.

### Technical Explanation
Layered runtime architecture:
`API -> Services/Agents -> Database`

API layer:
- App bootstrap and middleware: `app/main.py:18`
- Mounted v1 router: `app/api/v1/router.py:9`
- Main runtime routes: `app/api/v1/endpoints.py:59`

Agent/service layer:
- Stage agents: `app/agents/*.py`
- Business services: `app/services/*.py`

Data layer:
- Session management: `app/database/db.py:73`
- State handlers: `app/database/db_handler.py:53`
- ORM schema: `app/database/models.py:24`

Mounted vs non-mounted v1 route modules:
Mounted in runtime router:
- `app/api/v1/endpoints.py`
- `app/api/v1/auth.py`

Present but not mounted by `app/api/v1/router.py:10-11`:
- `app/api/v1/agents.py`
- `app/api/v1/runs.py`
- `app/api/v1/reviews.py`
- `app/api/v1/prompts.py`
- `app/api/v1/health.py`

Key design decisions visible in code:
1. Explicit queue handoff from API: `execute_agent_task.delay(...)` used in `app/api/v1/endpoints.py:71`.
2. Sequential scheduler execution with failure stop: `_run_sequential_pipeline()` in `app/tasks/scheduler.py:98`.
3. Human review gate semantics in persistence layer: `save_draft()` does not advance lead status (`app/database/db_handler.py:94`).
4. Fallback-first resilience: DB fallback (`app/database/db.py:103`), Celery fallback (`app/tasks/celery_app.py:11`), LLM empty-string failure contract (`app/services/llm_client.py:29`).

## 6. Control Flow

### API-triggered control flow
1. Request enters FastAPI and passes middleware (rate limit, correlation).
2. AuthZ helpers validate scopes (`app/api/v1/_authz.py:20`).
3. Endpoint handler calls service, orchestrator, or task enqueue.
4. DB session used for reads/writes with tenant scope.
5. Response serialized to JSON.

### Scheduler-triggered control flow
1. Celery beat triggers `automated_pipeline_run_task()` (`app/tasks/scheduler.py:193`).
2. Enabled/guard checks: `_is_pipeline_enabled()` and `_check_active_pipeline_run()`.
3. Lead scrape via `LeadScraperService.acquire_and_persist()`.
4. Sequential agent run: SDR -> Sales -> Negotiation -> Finance.
5. Run status updates and exit with result envelope.

### Review gate control flow
Drafts are saved without progression; explicit decision functions apply transitions:
- `mark_review_decision()` for leads.
- `mark_contract_decision()` for contracts.
- `mark_dunning_decision()` for invoices.

## 13. Security & Access Control
Authentication:
- JWT access/refresh tokens in `app/auth/jwt.py`.
- Token decode and validation in `_authz.authorize()` (`app/api/v1/_authz.py:20`).

Authorization:
- RBAC checks in `app/auth/rbac.py`.
- Scope enforcement in endpoint helpers (`app/api/v1/_authz.py`).

Tenant isolation:
- `tenant_id` on all key models (`app/database/models.py`).
- Tenant-scoped queries in CRM/service layer (`app/services/crm_service.py`).

Transport and rate limits:
- Rate limiting middleware (`app/middleware/rate_limit.py`).
- Correlation IDs for traceability (`app/middleware/correlation.py`).
