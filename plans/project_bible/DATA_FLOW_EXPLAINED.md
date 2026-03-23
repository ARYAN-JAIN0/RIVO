# DATA FLOW EXPLAINED

## 5. Data Flow

### Simple Explanation
Data enters RIVO from API requests or scheduler jobs. It then moves through stage-specific logic and is saved in database tables (`leads`, `deals`, `contracts`, `invoices`).
Drafts are generated automatically, but final progression is controlled by review decisions.

### Technical Explanation

#### Flow A: API `POST /api/v1/lead-acquisition`
Source: `app/api/v1/endpoints.py:65`
1. Request hits mounted endpoint.
2. Auth scope validated via `app/api/v1/_authz.py:20`.
3. `LeadAcquisitionService.acquire_and_persist(tenant_id)` called.
4. Service computes daily cap and scrapes/validates candidates.
5. Leads persisted with `status=New`, `review_status=New`, `source=scraped`.
6. API returns created/skipped counters.

Transformation points:
- Raw text -> normalized website/email/industry in `lead_acquisition_service`.

Storage points:
- `Lead` rows in `app/database/models.py`.

#### Flow B: API `POST /api/v1/pipeline/run` (queue path)
Source: `app/api/v1/endpoints.py:80`
1. Endpoint authenticates `agents.pipeline.run`.
2. Enqueues Celery `run_pipeline_task.delay(...)`.
3. Fan-out enqueues individual agent tasks (sdr, sales, negotiation, finance).
4. Each agent task calls `execute_registered_task()`.
5. Registry resolves callable from `app/tasks/registry.py`.
6. Agent executes and mutates DB via handlers/services.

Storage points:
- `AgentRun` rows (`app/database/models.py:289`).
- Entity updates in lead/deal/contract/invoice tables.
- `EmailLog` and `LLMLog` where applicable.

#### Flow C: Scheduler automated pipeline
Primary task: `automated_pipeline_run_task()` in `app/tasks/scheduler.py:193`
1. Feature flag guard (`_is_pipeline_enabled()`).
2. Concurrency guard (`_check_active_pipeline_run()`).
3. Create `AgentRun` row for automated pipeline.
4. Acquire leads via `LeadScraperService.acquire_and_persist()`.
5. If new leads exist, execute `_run_sequential_pipeline()`.
6. Sequentially execute `sdr -> sales -> negotiation -> finance`, stop on first failure.
7. Update run status and return result envelope.

#### Stage Data Movement: Lead -> Deal -> Contract -> Invoice

1) Lead stage (SDR)
- Read: `fetch_leads_by_status("New")` (`app/database/db_handler.py:53`).
- Transform: negative gate, signal score, email generation + structure validation.
- Write: draft + confidence + review status via `save_draft()`; progression only by `mark_review_decision()`.

2) Deal stage (Sales)
- Read: contacted leads query in `app/agents/sales_agent.py:26`.
- Transform: value/margin/segment/probability scoring; optional RAG context retrieval.
- Write: create/update `Deal` via `SalesIntelligenceService`; stage transition via `transition_stage()`.

3) Contract stage (Negotiation)
- Read: deals by `Proposal Sent`.
- Transform: objection classification, strategy generation, negotiation turn management.
- Write: contract creation and draft update; signed status only by `mark_contract_decision()`.

4) Invoice stage (Finance)
- Read: signed contracts.
- Transform: overdue calculation and dunning stage mapping.
- Write: invoice create, overdue update, dunning draft, paid mark via db handler functions.

#### Explicit Review Checkpoints
1. Lead draft approval/rejection: `mark_review_decision()`.
2. Contract negotiation approval/rejection: `mark_contract_decision()`.
3. Dunning approval/rejection: `mark_dunning_decision()`.

Audit trail path:
`_audit_review()` in `app/database/db_handler.py` writes to `ReviewAudit`.
