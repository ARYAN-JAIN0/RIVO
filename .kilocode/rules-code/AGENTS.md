# Code Mode Rules

## Database Session Management
Always use `get_db_session()` context manager - never create sessions directly:
```python
from app.database.db import get_db_session
with get_db_session() as session:
    # queries here
```

## Enum Values
Use title case strings for status values: `"New"`, `"Contacted"`, `"Qualified"`, `"Disqualified"` - NOT lowercase. See [`app/core/enums.py`](app/core/enums.py).

## LLM Integration
Import and use [`call_llm()`](app/services/llm_client.py:29) for all LLM calls:
```python
from app.services.llm_client import call_llm
response = call_llm(prompt, json_mode=True)  # for structured output
if response:  # CRITICAL: check for empty string failure
    data = json.loads(response)
else:
    # use fallback logic
```

## Email Validation
Before saving AI-generated emails, validate with [`validate_structure()`](app/utils/validators.py:39):
```python
from app.utils.validators import validate_structure, contains_forbidden_tokens
if not validate_structure(email_text):
    # reject email
```

## Service Classes
Extend [`BaseService`](app/services/base_service.py) for new services - it provides context manager support and transaction handling.

## Test Isolation
When writing tests, use the `isolated_session_factory` fixture from [`tests/conftest.py`](tests/conftest.py) for database isolation. Tests create isolated SQLite databases in `.test_tmp/` directory.

## Review Gate Pattern
When saving SDR drafts, use [`save_draft()`](app/database/db_handler.py:94) - it does NOT modify lead status. Only [`mark_review_decision()`](app/database/db_handler.py) can advance leads to Contacted status.

## SDR Negative Gate
Before processing leads in SDR agent, check [`check_negative_gate()`](app/agents/sdr_agent.py:45) which rejects:
- Leads with "layoff" or "competitor" in negative_signals
- Forbidden sectors: government, academic, education, non-profit, ngo
- Leads contacted within 30 days

## Safe JSON Parsing
Use [`safe_parse_json()`](app/core/schemas.py:55) for LLM responses:
```python
from app.core.schemas import safe_parse_json
data = safe_parse_json(llm_response, default={"score": 0})
```

## Tenant Isolation
All new entities must include `tenant_id` (default=1). Unique constraints are tenant-scoped. See [`app/database/models.py`](app/database/models.py).
