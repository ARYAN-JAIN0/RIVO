# MAINTENANCE GUIDE

## Simple Explanation
When you modify RIVO, make changes at the correct layer and keep stage transitions safe:
- Add HTTP behavior in mounted API modules.
- Add business rules in services/agents.
- Add schema/state changes in models + migrations.
- Preserve review gate behavior for progression-critical actions.

## Technical Explanation

## Safe Change Playbooks

### 1) Add a new endpoint
1. Add handler in mounted module (`app/api/v1/endpoints.py` or `app/api/v1/auth.py`).
2. Reuse `_authorize()` and required scopes (`app/api/v1/endpoints.py:27`).
3. Use `get_db_session()` context manager for DB access (`app/database/db.py:73`).
4. Keep response payloads deterministic and tenant-scoped.
5. Add/update tests in API suites (`tests/test_phase2_api.py`, `tests/test_phase3_api_analytics.py`).

### 2) Add a new service behavior
1. Add logic in `app/services/`.
2. Keep orchestration concerns out of endpoint handler where possible.
3. Reuse existing enums from `app/core/enums.py` (title-case values).
4. If persistence changes stage semantics, update db handler transitions and tests.

### 3) Add or modify a model
1. Edit `app/database/models.py`.
2. Add migration and validate with `alembic upgrade head`.
3. Update handlers/services and tests for new required fields or constraints.
4. Ensure tenant isolation for new entities (`tenant_id` where applicable).

### 4) Add a new agent step
1. Implement function in `app/agents/`.
2. Register it in task registry if queue-executed (`app/tasks/registry.py:38`).
3. Wire sequencing in scheduler/orchestrator paths if needed.
4. Add run tracking and error handling consistency with `AgentRun` records.

## Caution Zones

### Enum semantics are title-case
- Source: `app/core/enums.py:20`
- Pitfall: lowercase values can silently break filtering/transition logic.

### Review-gate transition rules
- `save_draft()` does not advance lead status: `app/database/db_handler.py:94`
- Actual lead progression occurs via `mark_review_decision()`: `app/database/db_handler.py:129`
- Similar pattern exists for contracts/invoices.

### Tenant isolation
- API uses token-derived tenant context (`app/api/v1/_authz.py:20`).
- CRM service enforces tenant ownership checks (`app/services/crm_service.py:313`, `app/services/crm_service.py:530`).

### Scheduler concurrency checks
- Guard against concurrent pipeline runs: `_check_active_pipeline_run()` (`app/tasks/scheduler.py:50`).

### Fallback modes
- Database fallback to SQLite when optional: `app/database/db.py:103`
- Celery fallback wrappers when Celery missing: `app/tasks/celery_app.py:11`
- LLM returns empty string on failure and requires caller fallback: `app/services/llm_client.py:29`
- RAG hash embedding fallback: `app/services/rag_service.py:101` and provider fallback in `app/services/rag_service.py:324`

## Test Mapping by Change Type

### Endpoint/auth changes
- `tests/unit/auth/test_auth_api.py`
- `tests/test_phase2_api.py`

### Stage transition and review changes
- `tests/test_db_handler.py`
- `tests/test_orchestrator.py`
- `tests/integration/test_automated_pipeline.py`

### Scheduler/queue changes
- `tests/unit/test_scheduler.py`
- `tests/integration/queue/test_agent_task_wrapper.py`

### Sales scoring/analytics changes
- `tests/test_phase3_sales_intelligence.py`
- `tests/test_phase3_api_analytics.py`

### Scraping/validation changes
- `tests/unit/services/test_lead_scraper_service.py`
- `tests/unit/schemas/test_scraper_schema.py`

## Maintenance Checklist Before Merge
1. Verify mounted routes still match intended runtime surface.
2. Verify state transition tests pass.
3. Verify tenant boundaries for all new reads/writes.
4. Verify fallback behavior still deterministic under dependency failure.
5. Verify no direct status progression bypasses review gate semantics.
