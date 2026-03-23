# MODULE DEEP DIVE

## 7. Core Modules & Responsibilities

### Lead Acquisition Modules
`app/services/lead_acquisition_service.py`
Purpose: public-source lead ingestion with minimal setup.
Key flow: count daily cap, scrape, validate/normalize, persist deduplicated leads.

`app/services/lead_scraper_service.py`
Purpose: production-oriented lead scraping and validation.
Key flow: resolve sources, rate-limit fetches, schema validation, persistence with duplication safeguards.

### SDR Module
`app/agents/sdr_agent.py`
Purpose: evaluate new leads and produce outreach drafts.
Key flow: negative gate, signal scoring, LLM generation with fallback, structure validation, draft save.

### Sales Module
`app/agents/sales_agent.py`
Purpose: convert contacted leads into scored deals.
Key flow: create/update deals, apply scoring, optional RAG retrieval, stage transition to proposal.

`app/services/sales_intelligence_service.py`
Purpose: centralized sales math and stage transition policy.
Key functions: `create_or_update_deal()`, `transition_stage()`, `calculate_margin()`.

### Negotiation Module
`app/agents/negotiation_agent.py`
Purpose: objection-response strategy generation and negotiation turn control.
Key flow: select proposal-sent deals, create/get contracts, classify objections, generate strategy, persist draft for review.

### Finance Module
`app/agents/finance_agent.py`
Purpose: invoice issuance and dunning sequence generation.
Key flow: find signed contracts, create invoices idempotently, compute overdue stage, generate dunning, persist drafts.

### Database Access Modules
`app/database/db.py`
Purpose: engine/session management with optional SQLite fallback.
Key functions: `_build_engine()`, `get_db_session()`, `verify_database_connection()`.

`app/database/db_handler.py`
Purpose: explicit state transition and review workflow mutations.
Key functions: `save_draft()`, `mark_review_decision()`, `mark_contract_decision()`, `mark_dunning_decision()`.

`app/database/models.py`
Purpose: ORM definitions for leads, deals, contracts, invoices, logs, tenants/users.

### Task and Scheduler Modules
`app/tasks/agent_tasks.py`
Purpose: queue wrapper around agent execution with retry bookkeeping.
Key functions: `execute_registered_task()`, `execute_agent_task()`, `run_pipeline_task()`.

`app/tasks/scheduler.py`
Purpose: autonomous scrape+pipeline orchestration with concurrency guard.
Key functions: `_run_sequential_pipeline()`, `automated_pipeline_run_task()`.

`app/tasks/celery_app.py`
Purpose: Celery app configuration and local fallback behavior.

### AI/RAG Modules
`app/services/opportunity_scoring_service.py`
Purpose: hybrid rule + LLM probability scoring.

`app/services/rag_service.py`
Purpose: semantic context storage/retrieval with embedding fallback.

## 9. Business Logic & Rules

### Review Gate Semantics
Drafts do not advance status. Progression is controlled only by decision functions:
- Lead progression via `mark_review_decision()`.
- Contract progression via `mark_contract_decision()`.
- Dunning progression via `mark_dunning_decision()`.

### SDR Negative Gate Checks
Leads are blocked for negative signals or forbidden sectors and if contacted within 30 days.

### SDR Signal Scoring
Signal scoring weights:
- Growth signals: +30
- Tech change signals: +25
- Decision maker role: +20
- ICP fit: +15
- Urgency: +10

### Thresholds
SDR: review queue threshold 85, auto-send threshold 92 (not implemented), signal threshold 60.
Negotiation: approval threshold 85, max turns 3.
Finance: dunning approval threshold 85.

### Email Validation
`validate_structure()` enforces greeting, sign-off, minimum word count, and forbids placeholder tokens.

### Tenant Isolation
All entities have `tenant_id` with tenant-scoped uniqueness constraints.
