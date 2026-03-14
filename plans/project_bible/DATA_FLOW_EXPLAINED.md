# DATA FLOW EXPLAINED

## Simple Explanation
Data enters RIVO from API requests or scheduler jobs. It then moves through stage-specific logic and is saved in database tables (`leads`, `deals`, `contracts`, `invoices`).

The most important rule: drafts are generated automatically, but final progression is controlled by review decisions.

## Technical Explanation

## Flow A: API `POST /api/v1/lead-acquisition`
Source: `app/api/v1/endpoints.py:65`

1. Request hits mounted endpoint.
2. Auth scope validated (`agents.sdr.run`) via `app/api/v1/_authz.py:20`.
3. `LeadAcquisitionService.acquire_and_persist(tenant_id)` called.
4. Service computes daily cap and scrapes/validates candidates (`app/services/lead_acquisition_service.py:158`).
5. Persisted rows inserted into `Lead` table with:
   - `status = New`
   - `review_status = New`
   - `source = scraped`
6. API returns created/skipped counters.

Transformation points:
- raw text -> normalized website/email/industry in `lead_acquisition_service` helpers.

Storage points:
- `Lead` rows in `app/database/models.py:24`.

## Flow B: API `POST /api/v1/pipeline/run` (queue path)
Source: `app/api/v1/endpoints.py:80`

1. Endpoint authenticates `agents.pipeline.run`.
2. Enqueues Celery `run_pipeline_task.delay(...)` from `app/tasks/agent_tasks.py:203`.
3. Fan-out enqueues individual agent tasks (`sdr`, `sales`, `negotiation`, `finance`).
4. Each agent task calls `execute_registered_task()` (`app/tasks/agent_tasks.py:44`).
5. Task registry resolves callable from `app/tasks/registry.py:38`.
6. Agent executes and mutates DB through `db_handler` and services.

Transformation points:
- runtime payload -> task context (tenant_id/user_id/run_id/trace_id)
- model-specific text generation/scoring inside agents/services.

Storage points:
- `AgentRun` rows (`app/database/models.py:289`)
- entity updates in lead/deal/contract/invoice tables
- `EmailLog`/`LLMLog` where applicable.

## Flow C: Scheduler automated pipeline
Primary task: `automated_pipeline_run_task()` in `app/tasks/scheduler.py:193`

1. Check feature flag (`_is_pipeline_enabled()` at `app/tasks/scheduler.py:38`).
2. Resolve tenant and concurrent-run guard (`_check_active_pipeline_run()` at `app/tasks/scheduler.py:50`).
3. Create `AgentRun` row for automated pipeline.
4. Acquire leads via `LeadScraperService.acquire_and_persist()`.
5. If new leads exist, execute `_run_sequential_pipeline()`.
6. Sequentially execute `sdr -> sales -> negotiation -> finance`, stop on first failure.
7. Update run status and return result envelope.

Transformation points:
- source records -> `ScrapedLeadSchema` validation -> `Lead` model rows.

Storage points:
- `AgentRun` records for scheduler pipeline.
- lead/deal/contract/invoice status progression updates.

## Stage Data Movement: Lead -> Deal -> Contract -> Invoice

### 1) Lead stage (SDR)
- Read: `fetch_leads_by_status("New")` (`app/database/db_handler.py:53`)
- Transform:
  - negative gate
  - signal score
  - email generation + structure validation
- Write:
  - draft + confidence + review status via `save_draft()` (`app/database/db_handler.py:94`)
  - status transition only by `mark_review_decision()` (`app/database/db_handler.py:129`)

### 2) Deal stage (Sales)
- Read: contacted leads query in `app/agents/sales_agent.py:26`
- Transform:
  - value/margin/segment/probability scoring
  - optional RAG context retrieval
- Write:
  - create/update `Deal` via `create_or_update_deal()` (`app/services/sales_intelligence_service.py:70`)
  - stage transition via `transition_stage()` (`app/services/sales_intelligence_service.py:160`)

### 3) Contract stage (Negotiation)
- Read: deals by `Proposal Sent` via `fetch_deals_by_status()` (`app/database/db_handler.py:195`)
- Transform:
  - objection classification
  - strategy generation + confidence
  - negotiation turn management
- Write:
  - create contract via `create_contract()` (`app/database/db_handler.py:269`)
  - update negotiation draft via `update_contract_negotiation()` (`app/database/db_handler.py:310`)
  - signed status only by review decision function `mark_contract_decision()` (`app/database/db_handler.py:351`)

### 4) Invoice stage (Finance)
- Read: signed contracts via `fetch_contracts_by_status()` (`app/database/db_handler.py:301`)
- Transform:
  - due-date to overdue-day math
  - dunning stage mapping
  - dunning message generation
- Write:
  - invoice create via `create_invoice()` (`app/database/db_handler.py:375`)
  - overdue status update via `update_invoice_status()` (`app/database/db_handler.py:433`)
  - dunning draft via `save_dunning_draft()` (`app/database/db_handler.py:448`)
  - paid mark via `mark_invoice_paid()` (`app/database/db_handler.py:465`)

## Explicit Review Checkpoints
1. Lead draft approval/rejection: `mark_review_decision()`
2. Contract negotiation approval/rejection: `mark_contract_decision()`
3. Dunning approval/rejection: `mark_dunning_decision()`

Audit trail write path:
- `_audit_review()` at `app/database/db_handler.py:32` writes to `ReviewAudit` (`app/database/models.py:227`).
