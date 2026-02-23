# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Build/Test Commands
```bash
# Run all tests
pytest -q

# Run specific test groups (as used in CI)
pytest -q tests/unit tests/test_db_handler.py tests/test_orchestrator.py tests/test_orm_utils.py tests/test_validators.py
pytest -q tests/integration tests/test_pipeline_integration_scaffold.py
pytest -q tests/test_phase2_services.py tests/test_phase2_api.py

# Run single test file
pytest -q tests/unit/services/test_lead_service.py

# Lint (syntax check only)
python -m compileall app tests

# Database migrations
alembic upgrade head
alembic downgrade base
```

## Critical Project Patterns

### Enum Values Use Title Case
All status enums in [`app/core/enums.py`](app/core/enums.py) use title case values (e.g., `"New"`, `"Contacted"`, `"Qualified"`), NOT lowercase. This matches database values and UI usage.

### Database Session Pattern
Use `get_db_session()` context manager from [`app/database/db.py`](app/database/db.py):
```python
from app.database.db import get_db_session
with get_db_session() as session:
    # queries here
```
Services can extend [`BaseService`](app/services/base_service.py) which provides context manager support.

### LLM Client
Use [`call_llm()`](app/services/llm_client.py:29) from `app/services/llm_client.py`. It connects to Ollama with model configured via `OLLAMA_MODEL` env var (default: `qwen2.5:7b`).

**Important**: `call_llm()` returns empty string `""` on failure. Always check for truthy response before parsing:
```python
response = call_llm(prompt, json_mode=True)
if response:
    data = json.loads(response)
else:
    # Use fallback logic
```

### Email Validation
[`validate_structure()`](app/utils/validators.py:39) in `app/utils/validators.py` enforces:
- Must start with "hi ", "hello ", or "dear "
- Must end with sign-off ("best,", "regards,", etc.) or email address
- Minimum 30 words
- No placeholder tokens from `FORBIDDEN_TOKENS` list

### Agent Pipeline Flow
SDR → Sales → Negotiation → Finance (see [`RevoOrchestrator`](app/orchestrator.py:34))

```mermaid
graph LR
    A[SDR Agent] -->|Contacted| B[Sales Agent]
    B -->|Qualified| C[Negotiation Agent]
    C -->|Signed| D[Finance Agent]
```

### Agent Thresholds

| Agent | Threshold | Value | Purpose |
|-------|-----------|-------|---------|
| SDR | `REVIEW_QUEUE_THRESHOLD` | 85 | Minimum score to enter review queue |
| SDR | `AUTO_SEND_THRESHOLD` | 92 | Score for immediate send (not implemented) |
| SDR | `SIGNAL_THRESHOLD` | 60 | Minimum signal score to proceed |
| Negotiation | `NEGOTIATION_APPROVAL_THRESHOLD` | 85 | Confidence threshold for approval |
| Negotiation | `MAX_NEGOTIATION_TURNS` | 3 | Maximum negotiation rounds |
| Finance | `DUNNING_APPROVAL_THRESHOLD` | 85 | Confidence threshold for dunning approval |

### SDR Negative Gate Checks
[`check_negative_gate()`](app/agents/sdr_agent.py:45) filters leads before processing:
- Rejects leads with "layoff" or "competitor" in negative_signals
- Blocks forbidden sectors: government, academic, education, non-profit, ngo
- Skips leads contacted within 30 days

### SDR Signal Scoring
[`calculate_signal_score()`](app/agents/sdr_agent.py:75) scores leads:
- Growth signals (hiring/growing/expanding): +30
- Tech change signals (tech/install/stack/migration): +25
- Decision maker role (cto/ceo/vp/head/director/founder/ciso): +20
- ICP fit (1000/500/enterprise/mid-market company size): +15
- Urgency (budget/q4/immediate): +10

### Review Gate Semantics
[`save_draft()`](app/database/db_handler.py:94) does NOT modify lead progression status. Only [`mark_review_decision()`](app/database/db_handler.py) can move leads to Contacted status.

### Database Fallback Behavior
When `DB_CONNECTIVITY_REQUIRED=false` (default in development), the system automatically falls back to SQLite if PostgreSQL is unavailable. See [`_fallback_to_sqlite_if_optional()`](app/database/db.py:103).

### Test Database Isolation
Tests use `isolated_session_factory` fixture in [`tests/conftest.py`](tests/conftest.py) which creates isolated SQLite databases per test in `.test_tmp/` directory.

### Safe JSON Parsing
Use [`safe_parse_json()`](app/core/schemas.py:55) for LLM responses:
```python
from app.core.schemas import safe_parse_json
data = safe_parse_json(llm_response, default={"score": 0})
```

### Celery Fallback Mode
When Celery is not installed, a mock implementation runs tasks synchronously. Set `CELERY_TASK_ALWAYS_EAGER=true` for local synchronous execution. See [`app/tasks/celery_app.py`](app/tasks/celery_app.py).

### Tenant Isolation
All entities have `tenant_id` with default=1. Unique constraints are tenant-scoped (e.g., `uq_leads_tenant_email`). See [`app/database/models.py`](app/database/models.py).
