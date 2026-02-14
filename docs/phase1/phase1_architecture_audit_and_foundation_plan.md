# Revo Phase 1 – Architecture Audit and Foundation Plan

## Scope and execution boundaries
- This Phase 1 deliverable performs a deep repository audit and provides implementation-ready blueprints.
- No runtime behavior is changed in this phase; this document and associated blueprint files are planning artifacts to guide controlled migration.
- Goal: stabilize direction and remove architectural uncertainty before introducing FastAPI, JWT/RBAC, Celery, Redis, and RAG/PGVector.

---

## 1) Full architecture report

### 1.1 Current repository topology (as-is)
- `app/agents/`: 4 runnable procedural agents (`sdr`, `sales`, `negotiation`, `finance`).
- `app/orchestrator.py`: central runner for sequential pipeline and health summary.
- `app/database/`: SQLAlchemy models, engine/session setup, CRUD-style handler functions.
- `app/services/`: mixed maturity service classes + util services (`llm_client`, `email_sender`, invoice PDF generator).
- `app/multi_agent_dashboard.py`, `app/review_dashboard.py`: Streamlit UIs tightly coupled to DB handler layer.
- `memory/`: optional Chroma + NetworkX stores with graceful degradation.
- `migrations/`: Alembic baseline migration (`20260213_0001`).
- `workers/`: scheduler placeholder only.
- `tests/`: unit-level tests focused on safety gates and orchestration behavior.

### 1.2 What currently works
1. **Deterministic multi-stage pipeline runs end-to-end (script mode)**
   - `orchestrator.py` can run all agents in sequence and isolate agent failures.
2. **Human review gate exists across SDR/deal/contract/dunning artifacts**
   - Draft content persists with pending review semantics.
3. **Database core entities are functional**
   - `leads`, `deals`, `contracts`, `invoices`, `review_audit` with indexes and constraints.
4. **Alembic baseline exists and can bootstrap schema**
   - one baseline migration available.
5. **Structured JSON logging exists centrally**
   - startup + orchestrator + DB handler use event-style logging.
6. **Basic health check exists**
   - counts by status/pending review.
7. **LLM integration exists with retries/rate limiting**
   - Ollama HTTP call wrapper with JSON mode option.
8. **CI pipeline exists**
   - GitHub Actions runs pytest.
9. **Docker compose can run db + ollama + app + streamlit dashboard**
   - suitable for local demo environment.

### 1.3 What is partially working
1. **Service layer**
   - `BaseService`, `LeadService`, etc. exist but are not the primary execution path; agents still call `db_handler` directly.
2. **Memory subsystem (vector/graph)**
   - graceful fallback when deps are missing, but no consistent orchestration usage and no production persistence strategy.
3. **LLM output validation**
   - strong schema validation for some prompts; inconsistent across modules and not centralized.
4. **Dashboard orchestration control**
   - can approve/reject artifacts, but Streamlit directly mutates backend state.
5. **SMTP sender**
   - abstraction exists, but no persisted email logs / delivery audit trail / sandbox mode.
6. **Status enum consistency**
   - title-case enums are used, but long-term API interoperability requires canonical machine-safe enum values.

### 1.4 Stub / dummy / placeholder areas
1. `app/main.py`
   - comment indicates “later FastAPI”, currently runs SDR script entry point.
2. `workers/scheduler.py`
   - explicit placeholder file with no scheduler implementation.
3. `app/services/invoice_generator.py`
   - optional utility with print-based logging and standalone usage, not integrated into resilient workflows.
4. `db/schema.sql`
   - legacy SQL artifact not source-of-truth relative to ORM + Alembic.
5. Multiple `tmpclaude-*` files in repo root
   - environment artifacts, non-functional application assets.

### 1.5 Technical debt inventory
1. **Tight coupling across layers**
   - agents import DB handler functions directly and embed prompting/business decisions in procedural code.
2. **No API boundary for backend**
   - script + Streamlit invocation patterns dominate, limiting external control and scaling.
3. **No tenant model / tenant-aware filtering**
   - all reads/writes are global.
4. **No authn/authz**
   - zero JWT, role checks, or endpoint-level policy controls.
5. **No async/background queue abstraction**
   - long-running tasks block process; no retry orchestration metadata.
6. **Weak auditability for AI execution**
   - no dedicated `agent_runs` / `llm_logs` tables for traceability.
7. **Error handling is inconsistent**
   - broad catches with string logs; no centralized HTTP exception mapping.
8. **State transition logic dispersed**
   - status changes happen in handler functions and dashboard actions without unified state machine.
9. **Dependency management lacks lockfile and tiers**
   - single `requirements.txt`, optional deps commented, no extras split.
10. **Migration strategy not future-safe**
   - baseline migration exists, but no forward strategy for tenant partitioning, enums, row-level ownership.

### 1.6 Where scaling will break first
1. **Single-process sequential orchestration**
   - no queue and no worker pool.
2. **Dashboard direct DB mutation**
   - no API contracts, no access control, no concurrency safety.
3. **Global lead email uniqueness (not tenant-scoped)**
   - multi-tenant collisions unavoidable.
4. **Absence of idempotency tokens/run ids**
   - duplicate executions and replay ambiguity.
5. **No per-tenant/per-role isolation**
   - unacceptable for production SaaS security model.
6. **No centralized observability for LLM and agent performance**
   - impossible to govern cost/quality at scale.

---

## 2) Backend refactor plan (FastAPI migration)

## 2.1 Target backend layout
```text
app/
  core/
    config.py
    logging.py
    exceptions.py
    security.py
    dependencies.py
  api/
    v1/
      router.py
      health.py
      auth.py
      agents.py
      runs.py
      prompts.py
      reviews.py
  services/
    leads_service.py
    deals_service.py
    contracts_service.py
    invoices_service.py
    review_service.py
    run_service.py
  agents/
    base_agent.py
    sdr_agent.py
    sales_agent.py
    negotiation_agent.py
    finance_agent.py
  orchestration/
    pipeline_orchestrator.py
    run_manager.py
    state_machine.py
  models/
    base.py
    tenant.py
    user.py
    lead.py
    deal.py
    contract.py
    invoice.py
    negotiation_history.py
    email_log.py
    pipeline_stage.py
    agent_run.py
    llm_log.py
  schemas/
    auth.py
    common.py
    leads.py
    deals.py
    contracts.py
    invoices.py
    runs.py
    prompts.py
  tasks/
    celery_app.py
    registry.py
    agent_tasks.py
    hooks.py
  llm/
    client.py
    orchestrator.py
    prompt_templates/
    validators/
    scoring/
  rag/
    embeddings/
    vector_store/
    retrieval/
  auth/
    jwt.py
    rbac.py
    tenant_context.py
  utils/
    orm.py
    validators.py
    ids.py
```

### 2.2 Service-first refactor sequence
1. Introduce `BaseAgent` contract (`run(context) -> AgentResult`).
2. Move each procedural `run_*_agent` into class-based service-backed agent implementation.
3. Keep old entrypoints as thin compatibility wrappers during migration window.
4. Replace direct `db_handler` usage with service interfaces injected via FastAPI dependencies.
5. Isolate prompt generation/validation into `llm/` and remove prompt logic from agent body.
6. Decommission Streamlit->DB direct calls; Streamlit (or future frontend) must call API only.

### 2.3 Dependency injection strategy
- FastAPI dependency graph:
  - `get_settings()`
  - `get_db_session()`
  - `get_current_user()`
  - `get_tenant_context()`
  - `get_orchestrator()`
  - `get_agent_registry()`
- Services instantiated per-request with DB session + tenant context.
- Celery tasks instantiate services using shared container/factory.

### 2.4 Structured logging and exception strategy
- Log schema fields: `timestamp`, `level`, `event`, `tenant_id`, `user_id`, `run_id`, `agent_name`, `trace_id`.
- Global exception handlers:
  - validation -> 422
  - auth -> 401/403
  - domain conflicts -> 409
  - not found -> 404
  - unhandled -> 500 with opaque error code
- Correlation-id middleware required on all requests.

---

## 3) Database hardening plan (PostgreSQL + Alembic)

### 3.1 Existing table audit
- Existing core tables: `leads`, `deals`, `contracts`, `invoices`, `review_audit`, `alembic_version`.
- Gaps: no tenants/users/run logs/email logs/negotiation history/pipeline stage history.

### 3.2 New/expanded schema set
- `tenants`
- `users`
- `pipeline_stages`
- `negotiation_history`
- `email_logs`
- `agent_runs`
- `llm_logs`
- Extend `leads`, `deals`, `contracts`, `invoices` with `tenant_id`, audit stamps, soft delete.

### 3.3 Multi-tenant and integrity standards
- Every business row contains `tenant_id` FK.
- Unique constraints become tenant-scoped (`tenant_id + natural_key`).
- Add composite indexes for high-frequency filters:
  - `(tenant_id, status)`, `(tenant_id, stage)`, `(tenant_id, created_at)`.
- Enums become DB enums with migration-safe transitions.
- Add `created_at`, `updated_at`, `deleted_at` to all domain tables.

### 3.4 Proposed SQLAlchemy model set
- See: `docs/phase1/target_sqlalchemy_models.py`.

### 3.5 Alembic migration plan (ordered)
1. **Revision A**: create `tenants`, `users`; seed default tenant + admin bootstrap path.
2. **Revision B**: add `tenant_id` nullable to existing domain tables; backfill default tenant.
3. **Revision C**: enforce non-null `tenant_id`; convert unique constraints to tenant-scoped.
4. **Revision D**: create new tables (`pipeline_stages`, `negotiation_history`, `email_logs`, `agent_runs`, `llm_logs`).
5. **Revision E**: add `created_at/updated_at/deleted_at` and new indexes.
6. **Revision F**: migrate status columns to strict enum types and validate values.
7. **Revision G**: add pgvector extension/table(s) when RAG store is activated.

### 3.6 Data migration safeguards
- Run in maintenance window.
- Pre-migration snapshot and checksum counts.
- Backfill scripts with idempotent guards.
- Post-migration verification: row counts, FK integrity, enum validity.

---

## 4) Auth & RBAC foundation plan

### 4.1 JWT model
- Access token (short TTL) + refresh token (long TTL).
- Claims:
  - `sub` (user_id)
  - `tenant_id`
  - `role`
  - `permissions_version`
  - `exp`, `iat`, `jti`

### 4.2 Roles and permissions
- `Admin`: full tenant control, prompts, retries, overrides.
- `Sales`: sales + negotiation operations.
- `SDR`: SDR lead generation/review operations.
- `Finance`: invoice + dunning operations.
- `Viewer`: read-only metrics/logs.

### 4.3 Middleware/dependencies
- Tenant resolution priority:
  1) JWT claim `tenant_id`
  2) optional header override for admin-only support contexts
- RBAC check dependency: endpoint declares required scopes.
- Strict tenant filter injected into all service-level queries.

---

## 5) Queue & background architecture plan

### 5.1 Celery/Redis baseline
- Redis broker + result backend.
- Celery app with named queues:
  - `agents.sdr`
  - `agents.sales`
  - `agents.negotiation`
  - `agents.finance`
  - `agents.pipeline`

### 5.2 Task registry and wrappers
- Registry maps task key -> agent executor.
- Common wrapper responsibilities:
  - create `agent_runs` record
  - inject tenant/user context
  - run deterministic pre-checks
  - call LLM orchestration when needed
  - update status and structured logs

### 5.3 Retry/failure tracking
- Exponential backoff with capped retries.
- Persist `retry_count`, `error_payload`, `finished_at` in `agent_runs`.
- Dead-letter queue for repeated failures.

---

## 6) LLM & RAG foundation architecture

### 6.1 LLM orchestrator contract
- Unified interface:
  - `generate(prompt_key, context, tenant_id, run_id) -> LLMResult`
- Captures prompt hash, model, latency, token usage, confidence score.

### 6.2 Hybrid deterministic + LLM enforcement
1. Deterministic validator executes first (schema + policy checks).
2. LLM generation executes if deterministic gate passes.
3. Post-generation deterministic validator re-checks structure/content policy.
4. Confidence gate decides:
   - auto-queue human review
   - auto-approve only for explicitly allowed low-risk actions.

### 6.3 RAG modular design
```text
rag/
  embeddings/
    provider.py
    ollama_embedder.py
  vector_store/
    pgvector_store.py
  retrieval/
    retriever.py
    reranker.py
```
- Phase 1 only defines boundary contracts; ingestion/retrieval logic deferred.

---

## 7) Dashboard API preparation blueprint

### 7.1 Required API endpoints (backend only)
- `POST /api/v1/agents/{agent_name}/run`
- `POST /api/v1/pipeline/run`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `POST /api/v1/runs/{run_id}/retry`
- `GET /api/v1/logs/agents`
- `GET /api/v1/metrics/agents`
- `POST /api/v1/reviews/{entity_type}/{entity_id}/decision`
- `PATCH /api/v1/prompts/{prompt_key}`
- `POST /api/v1/runs/{run_id}/manual-override`

### 7.2 Request/response standards
- All endpoints require JWT and tenant context.
- Every mutating endpoint emits `run_id` or `audit_id`.
- Pagination standard for list endpoints.

---

## 8) Testing foundation blueprint

### 8.1 Test directories
```text
tests/
  unit/
    agents/
    services/
    auth/
    llm/
    validators/
  integration/
    api/
    db/
    queue/
  mocks/
    llm/
    smtp/
```

### 8.2 Mandatory test categories
- Unit:
  - state transitions
  - RBAC policy checks
  - deterministic validators
  - tenant filter enforcement
- Integration:
  - FastAPI endpoints with test DB
  - Alembic upgrade/downgrade path
  - Celery task execution + retry behavior
- Mock tests:
  - LLM response shaping/failure paths
  - SMTP sandbox mode and email logging

### 8.3 CI-ready strategy
- matrix: python 3.11
- services in CI: postgres + redis
- run order: lint -> unit -> integration -> migration checks

---

## Breaking changes (planned, explicit)
1. Status values will move from display strings to canonical enum values (`new`, `contacted`, etc.) at DB/API level.
2. Direct Streamlit DB writes will be removed; dashboard must call authenticated API.
3. Legacy script entrypoints become compatibility wrappers; primary runtime shifts to FastAPI + Celery.
4. Global uniqueness (e.g., lead email) changes to tenant-scoped uniqueness.
5. DB model imports move from `app/database/models.py` to modular `app/models/*` package.
6. Some handler function signatures will require `tenant_id` and actor context.

---

## Manual tasks required from user
1. Provide production secrets and env values:
   - JWT secret/private key
   - DB credentials
   - Redis credentials
   - SMTP credentials
2. Confirm tenant bootstrap strategy:
   - default tenant naming
   - admin bootstrap user email
3. Decide canonical status enum policy (machine-safe lowercase required recommendation).
4. Approve migration downtime window for tenant backfill/enforcement revisions.
5. Confirm infrastructure targets for deployment:
   - Docker Compose only vs Kubernetes-ready conventions
6. Confirm Qwen 7B runtime mode:
   - Ollama local model path / GPU availability / fallback policy
7. Provide allowed auto-approval policy boundaries for confidence-gated actions.

---

## Validation checklist for this phase
- [x] Repository audited across architecture, agents, orchestrator, DB, migrations, dashboard, LLM, SMTP, logging, errors, dependencies.
- [x] Target backend folder architecture defined.
- [x] Updated SQLAlchemy model blueprint produced.
- [x] Alembic migration sequence plan produced.
- [x] Auth + RBAC backend foundation specified.
- [x] Queue/background architecture specified.
- [x] LLM + RAG architecture contracts specified.
- [x] API blueprint for dashboard readiness provided.
- [x] Testing structure blueprint provided.
- [x] Breaking changes and manual user tasks explicitly listed.

## Updated folder structure (after this phase)
```text
docs/
  phase1/
    phase1_architecture_audit_and_foundation_plan.md
    target_sqlalchemy_models.py
```

**Phase 1 Completed – Ready for Phase 2**
    alembic_migration_sequence_plan.md
    phase1_architecture_audit_and_foundation_plan.md
    phase1_execution_log.md
    target_sqlalchemy_models.py
```

Execution evidence is recorded in:
- `docs/phase1/phase1_execution_log.md`

**Phase 1 Completed - Ready for Phase 2**
