# FILE STRUCTURE GUIDE

## 2. Complete File & Folder Map

Top-level groups:
`app/` (core runtime), `tests/`, `scripts/`, `migrations/`, `plans/`, `docs/`, `config/`, `memory/`, `utils/`, `workers/`, `certs/`, `proposals/`, plus root configs and scripts.

Deterministic inventory scope:
- Source-controlled and repo-local files enumerated by `rg --files`, plus explicit hidden/tooling files and runtime artifacts in root.
- Excluded: `.git/` and `.venv/` directories (environment/VC metadata, non-repo code).

Artifact metadata (size, mtime, SHA256):
| Path | Size (bytes) | LastWriteTime | SHA256 |
| --- | --- | --- | --- |
| `celerybeat-schedule.bak` | 89 | 2026-02-20 14:44:51 | 63F5B26FAABBF4E348EA08D669235518DEF03E21BDF4F7A6EB80DB363A353D6B |
| `celerybeat-schedule.dat` | 1540 | 2026-02-20 14:44:51 | A49A3A21D3EAE753BAC6E7CB82E7AC0051BCF5094355E2FEC07BD1D23B24DFBD |
| `celerybeat-schedule.dir` | 89 | 2026-02-20 14:44:51 | 63F5B26FAABBF4E348EA08D669235518DEF03E21BDF4F7A6EB80DB363A353D6B |
| `rivo.backup_20260215_055431.db` | 229376 | 2026-02-15 11:24:31 | 31F521728129D8929A92796CE65866BB063F32F4CC2E47D0F8F3753A41BACE9A |
| `rivo.db` | 200704 | 2026-02-16 11:00:55 | 1EAA168BB88AC206F7D458BA22312707F67BB76F105F6C83BAF0302C8506079E |
| `rivo_local.db` | 98304 | 2026-02-14 20:25:12 | 8CD42C4E5C8CAE1447BECB7985388FA4B98F611A743D40F6F22C0B0D0CA6F854 |
| `rivo_phase2_gate.db` | 225280 | 2026-02-14 23:33:31 | BDBBF52FE8AA485DE781E9C02C3CDD6C85AFC462D56056D8CED7B70F6C3C01D7 |
| `rivo.log` | 1041779 | 2026-02-24 21:01:14 | E890FCFDB35C4E66F4977CA762C9A0FC319CF9EF0CD68D3FB2F45691C6E779CD |
| `scheduler.log` | 496232 | 2026-02-24 01:07:07 | 5D6276C50FC76DDA1726FFE983FD03C64BB0C3DBEE9A986EDD87B79B2CB8424A |
| `tls_uvicorn.err.log` | 203 | 2026-02-20 10:44:33 | E7C01911654D91229E1FD37A47FA31E90572200D272F4D0FEA0DEB2389A8D23D |
| `tls_uvicorn.out.log` | 1694 | 2026-02-20 10:44:36 | F9FD236E6DEE72BF86AC8DEC3F2145480B61642B555541F99D807D01DFF99D74 |
| `proposals/proposal_deal_12_v1.pdf` | 2062 | 2026-02-19 11:15:45 | A0972CD2D51057422A63EC73F6C4E0A5518A56E6F284EBF358B29E3CFA394D8E |
| `certs/localhost-key.pem` | 3324 | 2026-02-20 10:43:21 | E3A80632C512EAA5410C083CFA728035E1F4532289333B2DE7419C95C649B656 |
| `certs/localhost-cert.pem` | 1876 | 2026-02-20 10:43:21 | 259D78F5E72CB3C0345E6B76F1B44BA00772CA70B3BA741272DA9CE85B2040C4 |

## 3. File-by-File Breakdown

Category templates (apply to all files mapped to the category):

ASSISTANT_CONFIG
Purpose: assistant configuration. Inputs: JSON config. Outputs: assistant behavior settings. Key Components: config keys. Dependencies: assistant runtime. Internal Logic Summary: static configuration. Edge Cases: invalid keys.

ASSISTANT_RULES
Purpose: assistant prompts/rules. Inputs: markdown or text. Outputs: guidance for automation. Key Components: rule blocks. Dependencies: assistant runtime. Internal Logic Summary: static rules. Edge Cases: stale or conflicting rules.

CI_CONFIG
Purpose: CI workflow definitions. Inputs: YAML workflow. Outputs: CI jobs. Key Components: jobs/steps. Dependencies: CI runner. Internal Logic Summary: static pipeline config. Edge Cases: version drift or missing secrets.

IDE_CONFIG
Purpose: IDE/workspace settings. Inputs: JSON settings. Outputs: editor behavior. Key Components: editor settings. Dependencies: IDE. Internal Logic Summary: static config. Edge Cases: IDE version mismatch.

ROOT_ENV_CONFIG
Purpose: environment and ignore configuration. Inputs: env vars or ignore rules. Outputs: runtime configuration or git ignore behavior. Key Components: key-value pairs or ignore patterns. Dependencies: shell/git. Internal Logic Summary: static config. Edge Cases: missing envs or ignored files.

ROOT_DOCS
Purpose: repository documentation. Inputs: repo context. Outputs: guidance. Key Components: sections. Dependencies: none. Internal Logic Summary: static text. Edge Cases: drift from code.

ROOT_CONFIG
Purpose: build/runtime config. Inputs: config fields. Outputs: tooling config. Key Components: sections and keys. Dependencies: Docker/Alembic/Pytest/packaging tools. Internal Logic Summary: static configuration. Edge Cases: incompatible versions.

ROOT_SCRIPTS
Purpose: root-level execution scripts. Inputs: shell args and env. Outputs: executed commands and logs. Key Components: command sequence. Dependencies: Python and repo scripts. Internal Logic Summary: orchestrate local runs. Edge Cases: missing env or tooling.

ARTIFACTS
Purpose: runtime artifacts. Inputs: runtime state. Outputs: persisted logs/state. Key Components: binary or log content. Dependencies: runtime execution. Internal Logic Summary: environment-specific outputs. Edge Cases: stale data.

APP_ENTRYPOINT
Purpose: FastAPI application entrypoint. Inputs: environment config. Outputs: ASGI app instance. Key Components: `create_app`. Dependencies: FastAPI, router, middleware. Internal Logic Summary: app composition and route mounting. Edge Cases: misconfigured routes.

APP_ORCHESTRATOR_ENTRY
Purpose: CLI orchestrator. Inputs: CLI args and env. Outputs: stage run results. Key Components: `RevoOrchestrator`. Dependencies: agents and DB/services. Internal Logic Summary: sequential agent execution. Edge Cases: no-op stages.

APP_AGENTS
Purpose: agent stage execution. Inputs: DB records, config, LLM output. Outputs: drafts, status updates, logs. Key Components: stage functions. Dependencies: db_handler, services, validators, llm_client. Internal Logic Summary: fetch, score, generate, persist. Edge Cases: LLM failure and review-gate enforcement.

APP_API_CORE
Purpose: API router wiring. Inputs: router objects. Outputs: mounted routes. Key Components: router composition. Dependencies: FastAPI. Internal Logic Summary: compose routers. Edge Cases: unmounted modules.

APP_API_V1
Purpose: v1 endpoint handlers. Inputs: HTTP requests, headers, params. Outputs: JSON responses and task enqueue. Key Components: endpoint functions. Dependencies: services, auth, tasks. Internal Logic Summary: authorize, validate, dispatch. Edge Cases: auth failure, empty data.

APP_AUTH
Purpose: authentication and RBAC. Inputs: JWTs and secrets. Outputs: auth decisions and user context. Key Components: encode/decode, scope checks. Dependencies: core config. Internal Logic Summary: validate and authorize. Edge Cases: expired tokens.

APP_CORE
Purpose: core config, enums, logging. Inputs: env vars. Outputs: config objects, enums, exceptions. Key Components: config loader, enum types. Dependencies: pydantic/logging. Internal Logic Summary: centralize shared runtime state. Edge Cases: missing envs.

APP_DATABASE
Purpose: database engine/session/handlers. Inputs: DB URLs, session context. Outputs: queries and commits. Key Components: `get_db_session`, handler functions. Dependencies: SQLAlchemy, models. Internal Logic Summary: execute transitions and queries. Edge Cases: connectivity failures and fallback.

APP_MODELS
Purpose: ORM model definitions. Inputs: SQLAlchemy base. Outputs: tables and relationships. Key Components: model classes. Dependencies: SQLAlchemy, core enums. Internal Logic Summary: schema definition. Edge Cases: schema drift.

APP_SCHEMAS
Purpose: Pydantic schemas. Inputs: request payloads. Outputs: validated schema objects. Key Components: schema classes. Dependencies: pydantic, core enums. Internal Logic Summary: validation and serialization. Edge Cases: validation errors.

APP_SERVICES
Purpose: business logic and integrations. Inputs: DB sessions and external services. Outputs: domain mutations and results. Key Components: service methods. Dependencies: db/models, llm, rag. Internal Logic Summary: implement stage behavior. Edge Cases: external failures.

APP_TASKS
Purpose: task wrappers and scheduler. Inputs: task payloads/config. Outputs: run records and task results. Key Components: Celery tasks, scheduler functions. Dependencies: Celery, db_handler, orchestrator. Internal Logic Summary: queue and schedule execution. Edge Cases: concurrency guard.

APP_MIDDLEWARE
Purpose: rate limiting and correlation. Inputs: request/response cycle. Outputs: headers and early responses. Key Components: middleware dispatch. Dependencies: FastAPI/Starlette. Internal Logic Summary: enforce limits and IDs. Edge Cases: limit exceed.

APP_LLM
Purpose: LLM client/scoring/validators. Inputs: prompts and model output. Outputs: text or parsed scores. Key Components: LLM client and heuristics. Dependencies: HTTP client, config. Internal Logic Summary: call LLM, parse responses. Edge Cases: invalid JSON.

APP_RAG
Purpose: embeddings and retrieval. Inputs: text docs and queries. Outputs: embeddings and ranked results. Key Components: embedder, retriever, vector store. Dependencies: pgvector or fallback. Internal Logic Summary: similarity search. Edge Cases: missing embedder.

APP_ORCHESTRATION
Purpose: pipeline orchestration and state machine. Inputs: agent results and run context. Outputs: state transitions. Key Components: orchestrator and state machine. Dependencies: agents, services. Internal Logic Summary: coordinate multi-agent runs. Edge Cases: failed stage short-circuit.

APP_DASHBOARD
Purpose: Streamlit dashboards. Inputs: DB state and API calls. Outputs: interactive UI. Key Components: Streamlit layout. Dependencies: streamlit. Internal Logic Summary: render review and CRM views. Edge Cases: empty data.

MEMORY
Purpose: memory store implementations. Inputs: vectors/graph data. Outputs: stored memory and retrieval. Key Components: vector/graph store helpers. Dependencies: numpy or internal utils. Internal Logic Summary: local memory operations. Edge Cases: missing embeddings.

CONFIG_ROOT
Purpose: root config files. Inputs: config data. Outputs: configuration. Key Components: profile/settings. Dependencies: runtime configs. Internal Logic Summary: static configuration. Edge Cases: stale profiles.

DB_PACKAGE
Purpose: DB package marker. Inputs: none. Outputs: package namespace. Key Components: `__init__`. Dependencies: none. Internal Logic Summary: package marker. Edge Cases: none.

DOCS
Purpose: historical delivery/audit docs. Inputs: project context. Outputs: guidance. Key Components: sections. Dependencies: none. Internal Logic Summary: static text. Edge Cases: drift from code.

PLANS_DOCS
Purpose: design and implementation plans. Inputs: project decisions. Outputs: planning guidance. Key Components: plan sections. Dependencies: none. Internal Logic Summary: static text. Edge Cases: outdated assumptions.

PROJECT_BIBLE_DOCS
Purpose: Project Bible master documentation. Inputs: codebase behavior. Outputs: authoritative documentation. Key Components: structured sections. Dependencies: none. Internal Logic Summary: consolidated documentation. Edge Cases: must be kept in sync.

PROPOSALS
Purpose: proposal artifacts. Inputs: deal data. Outputs: PDFs. Key Components: rendered reports. Dependencies: report generator. Internal Logic Summary: static artifact. Edge Cases: stale proposal.

CERTS
Purpose: TLS certificate material. Inputs: TLS config. Outputs: cert/key. Key Components: PEM blocks. Dependencies: TLS tooling. Internal Logic Summary: static cert files. Edge Cases: expired certs.

SCRIPTS
Purpose: operational scripts. Inputs: CLI args, env, DB. Outputs: DB mutations or reports. Key Components: script logic. Dependencies: app modules. Internal Logic Summary: one-off ops. Edge Cases: missing DB.

TESTS
Purpose: pytest coverage. Inputs: fixtures and test data. Outputs: assertions. Key Components: test functions. Dependencies: pytest and app modules. Internal Logic Summary: validate behavior. Edge Cases: fixture isolation.

ROOT_UTILS
Purpose: root-level utilities. Inputs: python inputs. Outputs: helper outputs. Key Components: helper functions. Dependencies: app modules or stdlib. Internal Logic Summary: misc helpers. Edge Cases: drift from app utils.

WORKERS
Purpose: worker entrypoints. Inputs: task config. Outputs: worker execution. Key Components: scheduler runner. Dependencies: tasks and celery. Internal Logic Summary: background execution. Edge Cases: worker config mismatch.

MISC
Purpose: small package markers or lightweight helpers. Inputs: none or simple config. Outputs: module namespace or helpers. Key Components: module constants or helpers. Dependencies: stdlib or internal imports. Internal Logic Summary: minimal glue. Edge Cases: unused code.

File-to-category map (deterministic order):
```
.claude\settings.json | ASSISTANT_CONFIG
.env | ROOT_ENV_CONFIG
.env.example | ROOT_ENV_CONFIG
.github\workflows\ci.yml | CI_CONFIG
.gitignore | ROOT_ENV_CONFIG
.kilocode\rules-architect\AGENTS.md | ASSISTANT_RULES
.kilocode\rules-ask\AGENTS.md | ASSISTANT_RULES
.kilocode\rules-code\AGENTS.md | ASSISTANT_RULES
.kilocode\rules-code\rules.md | ASSISTANT_RULES
.kilocode\rules-debug\AGENTS.md | ASSISTANT_RULES
.kilocode\setup-script | ASSISTANT_RULES
.kilocode\system-prompt-code | ASSISTANT_RULES
.vscode\mcp.json | IDE_CONFIG
.vscode\settings.json | IDE_CONFIG
AGENTS.md | ROOT_DOCS
alembic.ini | ROOT_CONFIG
app\__init__.py | MISC
app\agents\__init__.py | APP_AGENTS
app\agents\base_agent.py | APP_AGENTS
app\agents\finance_agent.py | APP_AGENTS
app\agents\negotiation_agent.py | APP_AGENTS
app\agents\sales_agent.py | APP_AGENTS
app\agents\sdr_agent.py | APP_AGENTS
app\api\__init__.py | APP_API_CORE
app\api\_compat.py | APP_API_CORE
app\api\router.py | APP_API_CORE
app\api\v1\__init__.py | APP_API_V1
app\api\v1\_authz.py | APP_API_V1
app\api\v1\agents.py | APP_API_V1
app\api\v1\auth.py | APP_API_V1
app\api\v1\endpoints.py | APP_API_V1
app\api\v1\health.py | APP_API_V1
app\api\v1\prompts.py | APP_API_V1
app\api\v1\reviews.py | APP_API_V1
app\api\v1\router.py | APP_API_V1
app\api\v1\runs.py | APP_API_V1
app\auth\__init__.py | APP_AUTH
app\auth\jwt.py | APP_AUTH
app\auth\rbac.py | APP_AUTH
app\auth\tenant_context.py | APP_AUTH
app\config\__init__.py | MISC
app\config\scraper_sources.py | MISC
app\core\__init__.py | APP_CORE
app\core\config.py | APP_CORE
app\core\dependencies.py | APP_CORE
app\core\enums.py | APP_CORE
app\core\exceptions.py | APP_CORE
app\core\logging.py | APP_CORE
app\core\logging_config.py | APP_CORE
app\core\schemas.py | APP_CORE
app\core\security.py | APP_CORE
app\core\startup.py | APP_CORE
app\crm_dashboard.py | APP_DASHBOARD
app\database\__init__.py | APP_DATABASE
app\database\db.py | APP_DATABASE
app\database\db_handler.py | APP_DATABASE
app\database\init_db.py | APP_DATABASE
app\database\models.py | APP_DATABASE
app\llm\__init__.py | APP_LLM
app\llm\client.py | APP_LLM
app\llm\orchestrator.py | APP_LLM
app\llm\prompt_templates\__init__.py | APP_LLM
app\llm\prompt_templates\defaults.py | APP_LLM
app\llm\scoring\__init__.py | APP_LLM
app\llm\scoring\heuristics.py | APP_LLM
app\llm\validators\__init__.py | APP_LLM
app\llm\validators\basic.py | APP_LLM
app\main.py | APP_ENTRYPOINT
app\middleware\__init__.py | APP_MIDDLEWARE
app\middleware\correlation.py | APP_MIDDLEWARE
app\middleware\rate_limit.py | APP_MIDDLEWARE
app\models\__init__.py | APP_MODELS
app\models\agent_run.py | APP_MODELS
app\models\base.py | APP_MODELS
app\models\contract.py | APP_MODELS
app\models\deal.py | APP_MODELS
app\models\email_log.py | APP_MODELS
app\models\enums.py | APP_MODELS
app\models\invoice.py | APP_MODELS
app\models\lead.py | APP_MODELS
app\models\llm_log.py | APP_MODELS
app\models\negotiation_history.py | APP_MODELS
app\models\pipeline_stage.py | APP_MODELS
app\models\tenant.py | APP_MODELS
app\models\user.py | APP_MODELS
app\multi_agent_dashboard.py | APP_DASHBOARD
app\orchestration\__init__.py | APP_ORCHESTRATION
app\orchestration\pipeline_orchestrator.py | APP_ORCHESTRATION
app\orchestration\run_manager.py | APP_ORCHESTRATION
app\orchestration\state_machine.py | APP_ORCHESTRATION
app\orchestrator.py | APP_ORCHESTRATOR_ENTRY
app\rag\__init__.py | APP_RAG
app\rag\embeddings\__init__.py | APP_RAG
app\rag\embeddings\ollama_embedder.py | APP_RAG
app\rag\embeddings\provider.py | APP_RAG
app\rag\retrieval\__init__.py | APP_RAG
app\rag\retrieval\reranker.py | APP_RAG
app\rag\retrieval\retriever.py | APP_RAG
app\rag\vector_store\__init__.py | APP_RAG
app\rag\vector_store\pgvector_store.py | APP_RAG
app\schemas\__init__.py | APP_SCHEMAS
app\schemas\auth.py | APP_SCHEMAS
app\schemas\common.py | APP_SCHEMAS
app\schemas\contracts.py | APP_SCHEMAS
app\schemas\deals.py | APP_SCHEMAS
app\schemas\invoices.py | APP_SCHEMAS
app\schemas\leads.py | APP_SCHEMAS
app\schemas\prompts.py | APP_SCHEMAS
app\schemas\runs.py | APP_SCHEMAS
app\schemas\scraper.py | APP_SCHEMAS
app\services\base_service.py | APP_SERVICES
app\services\contract_service.py | APP_SERVICES
app\services\crm_service.py | APP_SERVICES
app\services\deal_service.py | APP_SERVICES
app\services\email_sender.py | APP_SERVICES
app\services\email_service.py | APP_SERVICES
app\services\invoice_generator.py | APP_SERVICES
app\services\invoice_service.py | APP_SERVICES
app\services\lead_acquisition_service.py | APP_SERVICES
app\services\lead_scraper.py | APP_SERVICES
app\services\lead_scraper_service.py | APP_SERVICES
app\services\lead_service.py | APP_SERVICES
app\services\llm_client.py | APP_SERVICES
app\services\opportunity_scoring_service.py | APP_SERVICES
app\services\proposal_service.py | APP_SERVICES
app\services\rag_service.py | APP_SERVICES
app\services\review_service.py | APP_SERVICES
app\services\run_service.py | APP_SERVICES
app\services\sales_intelligence_service.py | APP_SERVICES
app\tasks\__init__.py | APP_TASKS
app\tasks\agent_tasks.py | APP_TASKS
app\tasks\celery_app.py | APP_TASKS
app\tasks\hooks.py | APP_TASKS
app\tasks\registry.py | APP_TASKS
app\tasks\scheduler.py | APP_TASKS
app\utils\__init__.py | MISC
app\utils\ids.py | MISC
app\utils\orm.py | MISC
app\utils\validators.py | MISC
celerybeat-schedule.bak | ARTIFACTS
celerybeat-schedule.dat | ARTIFACTS
celerybeat-schedule.dir | ARTIFACTS
certs\localhost-cert.pem | CERTS
certs\localhost-key.pem | CERTS
CLEANUP_VERIFICATION_REPORT.md | ROOT_DOCS
config\__init__.py | CONFIG_ROOT
config\sdr_profile.py | CONFIG_ROOT
db\__init__.py | DB_PACKAGE
docker-compose.yml | ROOT_CONFIG
Dockerfile | ROOT_CONFIG
docs\phase1\alembic_migration_sequence_plan.md | DOCS
docs\phase1\phase1_architecture_audit_and_foundation_plan.md | DOCS
docs\phase1\phase1_execution_log.md | DOCS
docs\phase1\target_sqlalchemy_models.py | DOCS
docs\phase2\phase2_delivery_report.md | DOCS
docs\phase2\phase3_mandatory_preflight_tasks.md | DOCS
docs\phase3\phase3_delivery_report.md | DOCS
fix_stale_runs.py | ROOT_SCRIPTS
MANUAL_TASKS_REQUIRED.md | ROOT_DOCS
memory\__init__.py | MEMORY
memory\graph_store.py | MEMORY
memory\vector_store.py | MEMORY
migrations\env.py | MIGRATIONS
migrations\script.py.mako | MIGRATIONS
migrations\versions\20260213_0001_baseline_schema.py | MIGRATIONS
migrations\versions\20260214_0002_phase2_sdr_queue_email_foundation.py | MIGRATIONS
migrations\versions\20260215_0003_phase3_sales_intelligence.py | MIGRATIONS
migrations\versions\20260219_0004_contract_negotiation_turns.py | MIGRATIONS
migrations\versions\20260220_0005_users_auth_hardening.py | MIGRATIONS
plans\crm_dashboard_implementation_plan.md | PLANS_DOCS
plans\deal_explainability_panel_plan.md | PLANS_DOCS
plans\deal_explainability_ui_fix_plan.md | PLANS_DOCS
plans\deal_qualification_notes_design.md | PLANS_DOCS
plans\LEAD_SCRAPER_SCHEDULER_PRODUCTION_HARDENING_PLAN.md | PLANS_DOCS
plans\new_dashboard.md | PLANS_DOCS
plans\production-readiness-implementation-plan.md | PLANS_DOCS
plans\project_bible\AI_ALGORITHM_LOGIC.md | PROJECT_BIBLE_DOCS
plans\project_bible\DATA_FLOW_EXPLAINED.md | PROJECT_BIBLE_DOCS
plans\project_bible\DESIGN_RATIONALE.md | PROJECT_BIBLE_DOCS
plans\project_bible\FILE_STRUCTURE_GUIDE.md | PROJECT_BIBLE_DOCS
plans\project_bible\FUNCTION_REFERENCE.md | PROJECT_BIBLE_DOCS
plans\project_bible\MAINTENANCE_GUIDE.md | PROJECT_BIBLE_DOCS
plans\project_bible\MODULE_DEEP_DIVE.md | PROJECT_BIBLE_DOCS
plans\project_bible\PROJECT_OVERVIEW.md | PROJECT_BIBLE_DOCS
plans\project_bible\SIMPLIFIED_EXPLANATION.md | PROJECT_BIBLE_DOCS
plans\project_bible\SYSTEM_ARCHITECTURE.md | PROJECT_BIBLE_DOCS
plans\RIC_REPOSITORY_INTELLIGENCE_COMPILATION.md | PLANS_DOCS
plans\RIVO_RUNTIME_PIPELINE_ANALYSIS_REPORT.md | PLANS_DOCS
plans\rivo-phase1-3-implementation-audit-report.md | PLANS_DOCS
plans\rivo-stabilization-plan.md | PLANS_DOCS
proposals\proposal_deal_12_v1.pdf | PROPOSALS
pytest.ini | ROOT_CONFIG
README.md | ROOT_DOCS
requirements.txt | ROOT_CONFIG
rivo.backup_20260215_055431.db | ARTIFACTS
rivo.db | ARTIFACTS
rivo.log | ARTIFACTS
rivo_local.db | ARTIFACTS
rivo_phase2_gate.db | ARTIFACTS
run_full_pipeline.ps1 | ROOT_SCRIPTS
run_orchestrator_clean.bat | ROOT_SCRIPTS
run_pipeline_demo.py | ROOT_SCRIPTS
run_scheduler.py | ROOT_SCRIPTS
scheduler.log | ARTIFACTS
scripts\check_users.py | SCRIPTS
scripts\clear_database.py | SCRIPTS
scripts\create_db.py | SCRIPTS
scripts\postgres_phase2_permission_fix.sql | SCRIPTS
scripts\repair_deals_schema.py | SCRIPTS
scripts\repair_leads_schema.py | SCRIPTS
scripts\rivo_pg_safe_reset_ingest.py | SCRIPTS
scripts\seed_20_leads.py | SCRIPTS
scripts\seed_data.py | SCRIPTS
scripts\view_all_data.py | SCRIPTS
tests\conftest.py | TESTS
tests\integration\api\test_endpoint_blueprint_contract.py | TESTS
tests\integration\db\test_models_metadata.py | TESTS
tests\integration\queue\test_agent_task_wrapper.py | TESTS
tests\integration\test_automated_pipeline.py | TESTS
tests\mocks\llm\sample_response.json | TESTS
tests\mocks\smtp\sample_send_result.json | TESTS
tests\test_db_handler.py | TESTS
tests\test_orchestrator.py | TESTS
tests\test_orm_utils.py | TESTS
tests\test_phase2_api.py | TESTS
tests\test_phase2_regressions.py | TESTS
tests\test_phase2_services.py | TESTS
tests\test_phase3_api_analytics.py | TESTS
tests\test_phase3_sales_intelligence.py | TESTS
tests\test_pipeline_integration_scaffold.py | TESTS
tests\test_startup.py | TESTS
tests\test_validators.py | TESTS
tests\unit\agents\test_base_agent_contract.py | TESTS
tests\unit\auth\test_auth_api.py | TESTS
tests\unit\auth\test_jwt_rbac.py | TESTS
tests\unit\llm\test_llm_orchestrator.py | TESTS
tests\unit\schemas\test_scraper_schema.py | TESTS
tests\unit\services\test_contract_service.py | TESTS
tests\unit\services\test_crm_service.py | TESTS
tests\unit\services\test_deal_service.py | TESTS
tests\unit\services\test_invoice_service.py | TESTS
tests\unit\services\test_lead_scraper_service.py | TESTS
tests\unit\services\test_lead_service.py | TESTS
tests\unit\services\test_opportunity_scoring_service.py | TESTS
tests\unit\services\test_run_service.py | TESTS
tests\unit\test_config_ollama_urls.py | TESTS
tests\unit\test_rate_limit_middleware.py | TESTS
tests\unit\test_scheduler.py | TESTS
tests\unit\validators\test_domain_schema_validation.py | TESTS
tests\unit\validators\test_state_machine.py | TESTS
tls_uvicorn.err.log | ARTIFACTS
tls_uvicorn.out.log | ARTIFACTS
utils\orm.py | ROOT_UTILS
utils\validators.py | ROOT_UTILS
workers\scheduler.py | WORKERS
```
