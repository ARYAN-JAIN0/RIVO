# MAINTENANCE GUIDE

## Simple Explanation
Make changes at the correct layer and preserve review-gate semantics:
- Add HTTP behavior in mounted API modules.
- Add business rules in services/agents.
- Add schema/state changes in models + migrations.
- Preserve review gate behavior for progression-critical actions.

## 10. Error Handling & Failure Modes
LLM client returns empty string on failure; callers must fallback (`app/services/llm_client.py`).
Database connectivity may fall back to SQLite if optional (`app/database/db.py`).
Scheduler concurrency guard prevents overlapping runs (`app/tasks/scheduler.py`).
Review decisions are the only allowed progression path; bypassing causes state inconsistency.

## 11. Configuration & Environment
Environment variables are defined in `.env.example` and loaded in `app/core/config.py`.
Key categories:
- Database: `DATABASE_URL`, `DB_CONNECTIVITY_REQUIRED`.
- API: `API_HOST`, `API_PORT`, `API_PREFIX`.
- Auth: `JWT_SECRET`, `JWT_ACCESS_TTL_MINUTES`, `JWT_REFRESH_TTL_DAYS`.
- Queue: `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.
- LLM: `OLLAMA_*`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`.
- Email: `GMAIL_*`, `SMTP_SANDBOX_MODE`, `TRACKING_BASE_URL`.
- Rate limiting: `RATE_LIMIT_*`.
- Logging: `LOG_LEVEL`, `LOG_FILE`.

## Safe Change Playbooks
Add a new endpoint:
1. Add handler in mounted module (`app/api/v1/endpoints.py` or `app/api/v1/auth.py`).
2. Reuse `_authorize()` and required scopes.
3. Use `get_db_session()` for DB access.
4. Keep response payloads deterministic and tenant-scoped.
5. Add/update tests in API suites.

Add a new service behavior:
1. Add logic in `app/services/`.
2. Keep orchestration concerns out of endpoint handler where possible.
3. Reuse enums from `app/core/enums.py` (title-case values).
4. If persistence changes stage semantics, update db handler transitions and tests.

Add or modify a model:
1. Edit `app/database/models.py`.
2. Add migration and validate with `alembic upgrade head`.
3. Update handlers/services and tests.
4. Ensure tenant isolation for new entities.

Add a new agent step:
1. Implement function in `app/agents/`.
2. Register it in task registry if queue-executed (`app/tasks/registry.py`).
3. Wire sequencing in scheduler/orchestrator paths if needed.
4. Add run tracking and error handling.

## 15. Extension Guide
Preferred extension points:
- New business behavior: `app/services/`.
- New API capability: `app/api/v1/endpoints.py`.
- New schema fields: `app/database/models.py` plus migrations.
- New validation rules: `app/utils/validators.py` or `app/core/schemas.py`.

Compatibility rules:
- Keep enums title-cased.
- Do not bypass review-gate decision functions.
- Preserve tenant isolation on all reads/writes.

## 16. Debugging Playbook
Symptom: pipeline stalls after drafts created.
Check: review decision functions and review status fields in DB.

Symptom: scheduler not running.
Check: `_is_pipeline_enabled()` and Celery beat configuration.

Symptom: AI generation empty.
Check: `call_llm()` return value and fallback paths.

Symptom: API auth failures.
Check: JWT secret/config and `_authz.authorize()` scope mapping.

## Caution Zones
Enum semantics are title-case.
Review-gate transitions are authoritative in db_handler.
Tenant isolation must be preserved in all queries.
Fallback modes exist for DB, Celery, LLM, and RAG.
