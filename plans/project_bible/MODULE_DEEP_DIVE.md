# MODULE DEEP DIVE

## Simple Explanation
RIVO is split into modules where each module has one clear job:
- Acquire leads
- Work leads through SDR, Sales, Negotiation, Finance
- Persist and transition state safely
- Run automatically (scheduler/tasks) or manually (API)

## Technical Explanation

## 1) Lead Acquisition Modules

### `app/services/lead_acquisition_service.py`
- Problem solved: quick public-source lead ingestion with minimal setup.
- Internal flow:
  1. Count tenant daily lead volume (`_current_day_count()` at `app/services/lead_acquisition_service.py:117`)
  2. Scrape public pages (`scrape_public_leads()` at `app/services/lead_acquisition_service.py:127`)
  3. Validate/normalize and persist deduplicated leads (`acquire_and_persist()` at `app/services/lead_acquisition_service.py:158`)
- Key functions/classes:
  - `ScrapedLead` dataclass (`app/services/lead_acquisition_service.py:37`)
  - `LeadAcquisitionService` (`app/services/lead_acquisition_service.py:105`)
- Dependencies:
  - `get_db_session`, `Lead` model, `sanitize_text`, enums.
- Interactions:
  - API endpoint `POST /lead-acquisition` (`app/api/v1/endpoints.py:65`).

### `app/services/lead_scraper_service.py`
- Problem solved: stricter, production-oriented lead scraping/validation for scheduler flows.
- Internal flow:
  1. Resolve enabled sources and rate-limit fetches (`_fetch_from_source()` at `app/services/lead_scraper_service.py:344`)
  2. Validate via `ScrapedLeadSchema` (`_validate_lead()` at `app/services/lead_scraper_service.py:523`)
  3. Persist with duplicate safety (`_persist_leads()` at `app/services/lead_scraper_service.py:638`)
- Key classes:
  - `LeadScraperService` (`app/services/lead_scraper_service.py:181`)
  - `RateLimiter` (`app/services/lead_scraper_service.py:83`)
  - `ScraperMetrics` (`app/services/lead_scraper_service.py:130`)
- Interactions:
  - scheduler uses `acquire_and_persist()` (`app/tasks/scheduler.py:248` logic path).

## 2) SDR Module

### `app/agents/sdr_agent.py`
- Problem solved: evaluate new leads and produce outreach drafts with validation.
- Internal flow:
  1. Load `Lead.status == New` via `fetch_leads_by_status()`
  2. Run negative gate (`check_negative_gate()` at `app/agents/sdr_agent.py:45`)
  3. Score signals (`calculate_signal_score()` at `app/agents/sdr_agent.py:75`)
  4. Generate body (`generate_email_body()` at `app/agents/sdr_agent.py:138`)
  5. Inject signature and validate structure (`inject_signature()` at `app/agents/sdr_agent.py:166`)
  6. Save draft / auto-send branch (`run_sdr_agent()` at `app/agents/sdr_agent.py:215`)
- Dependencies:
  - LLM client, validators, db_handler, EmailService.
- Important behavior:
  - low-signal and blocked leads are disqualified.
  - stage changes rely on review decisions in persistence layer.

## 3) Sales Module

### `app/agents/sales_agent.py`
- Problem solved: convert contacted leads into scored deals and advance stage when qualified.
- Internal flow:
  1. Query contacted leads (`run_sales_agent()` at `app/agents/sales_agent.py:21`)
  2. Create/update deal via `SalesIntelligenceService`
  3. Retrieve RAG context (`RAGService.retrieve()`)
  4. If probability threshold met, transition to `Proposal Sent` and generate proposal.

### `app/services/sales_intelligence_service.py`
- Problem solved: centralized sales math + stage transition policy.
- Key functions:
  - `create_or_update_deal()` (`app/services/sales_intelligence_service.py:70`)
  - `transition_stage()` (`app/services/sales_intelligence_service.py:160`)
  - `calculate_margin()` (`app/services/sales_intelligence_service.py:42`)
- Dependencies:
  - `OpportunityScoringService`, `RAGService`, `ProposalService`, ORM models.

## 4) Negotiation Module

### `app/agents/negotiation_agent.py`
- Problem solved: objection-response strategy generation and negotiation turn control.
- Internal flow:
  1. Select `Proposal Sent` deals (`run_negotiation_agent()` at `app/agents/negotiation_agent.py:218`)
  2. Create/get contract (`create_contract()` in db_handler)
  3. Enforce max turns (`_is_max_turns_reached()` at `app/agents/negotiation_agent.py:205`)
  4. Classify objections (`classify_objections()` at `app/agents/negotiation_agent.py:74`)
  5. Generate strategy (`generate_objection_response()` at `app/agents/negotiation_agent.py:91`)
  6. Persist negotiation draft for review
- Dependencies:
  - db_handler contract functions, LLM client, validators.

## 5) Finance Module

### `app/agents/finance_agent.py`
- Problem solved: invoice issuance for signed contracts and dunning sequence generation.
- Internal flow:
  1. Find signed contracts (`run_finance_agent()` at `app/agents/finance_agent.py:148`)
  2. Create invoices idempotently (`create_invoice()` db_handler)
  3. Compute overdue days/stage (`calculate_days_overdue()` / `determine_dunning_stage()`)
  4. Generate dunning text (`generate_dunning_email()` at `app/agents/finance_agent.py:68`)
  5. Persist overdue update + pending review draft
- Dependencies:
  - db_handler invoice operations, LLM client.

## 6) Database Access Modules

### `app/database/db.py`
- Problem solved: database engine/session management with optional fallback for local resilience.
- Core operations:
  - engine build/rebind (`_build_engine()`, `_configure_engine()`)
  - runtime session context (`get_db_session()` at `app/database/db.py:73`)
  - startup connectivity + optional SQLite fallback (`verify_database_connection()` at `app/database/db.py:82`)

### `app/database/db_handler.py`
- Problem solved: explicit state transition and review workflow data mutations.
- Critical transition functions:
  - leads: `save_draft()` / `mark_review_decision()`
  - deals: `mark_deal_decision()`
  - contracts: `mark_contract_decision()`
  - invoices: `mark_dunning_decision()` / `mark_invoice_paid()`
- Design: each function opens its own DB session and commits locally.

### `app/database/models.py`
- Problem solved: normalized table model definitions and indexes.
- Major entities:
  - `Lead`, `Deal`, `Contract`, `Invoice`, `ReviewAudit`, `AgentRun`, `EmailLog`, `LLMLog`, tenant/auth entities.

## 7) Task and Scheduler Modules

### `app/tasks/agent_tasks.py`
- Problem solved: queue wrapper around agent execution with retry bookkeeping and run tracking.
- Key logic:
  - `execute_registered_task()` at `app/tasks/agent_tasks.py:44`
  - Celery task wrapper `execute_agent_task()` at `app/tasks/agent_tasks.py:147`
  - fan-out pipeline queue task `run_pipeline_task()` at `app/tasks/agent_tasks.py:203`

### `app/tasks/scheduler.py`
- Problem solved: autonomous scrape+pipeline orchestration with concurrency guard.
- Key logic:
  - gate/lock checks (`_is_pipeline_enabled()`, `_check_active_pipeline_run()`)
  - sequential run executor (`_run_sequential_pipeline()`)
  - top-level scheduled task (`automated_pipeline_run_task()`)

### `app/tasks/celery_app.py`
- Problem solved: Celery app configuration and local fallback behavior when Celery import is unavailable.
- Key logic:
  - beat schedule injection (`configure_beat_schedule()`)
  - task module registration (`register_task_modules()`)

## 8) AI/RAG Scoring Modules

### `app/services/opportunity_scoring_service.py`
- Problem solved: probability scoring with deterministic factors and optional LLM signal.
- Key functions:
  - `_rule_score()`, `_llm_score()`, `score()`.

### `app/services/rag_service.py`
- Problem solved: semantic context storage/retrieval with model fallback.
- Key functions:
  - `ingest_knowledge()`
  - `retrieve()`
  - provider fallback to hash embedding when Ollama is unavailable.

## Module Interaction Sequence (runtime)
1. Endpoint/task trigger -> agent function call.
2. Agent invokes service helpers.
3. Service/data handlers read/write ORM models.
4. Review status updated; progression happens only through decision functions.
