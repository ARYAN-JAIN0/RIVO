# Code Mode Rules (Non-Obvious Only)

## Import Rules
- Models: ONLY from `app.database.models`, NEVER from `app.models` (different Base class, not wired to Alembic)
- Enums: ONLY from `app.core.enums`, NEVER from `app.models.enums` (different subclass type)
- API modules: Import from `app.api._compat`, not directly from `fastapi`
- Do NOT add `sys.path.insert(0, PROJECT_ROOT)` to new files — this is legacy

## Session & Data
- `get_db_session()` does NOT auto-commit — call `session.commit()` explicitly
- `get_db()` is for FastAPI dependency injection (yield); `get_db_session()` is the `with`-statement context manager for agents/services
- `BaseService(db=None)` creates an unmanaged session — always pass a session or use context manager
- `call_llm()` returns `""` on failure, not None — check truthiness before `json.loads()`
- Use `safe_parse_json()` from `app.core.schemas` for LLM response parsing

## Enum Gotchas
- All status enums use title case (`"New"`, `"Contacted"`) EXCEPT `ReviewStatus` which has ALL_CAPS: `"STRUCTURAL_FAILED"`, `"BLOCKED"`, `"SKIPPED"`
- `FORBIDDEN_TOKENS` (8 items in `app/utils/validators.py`) ≠ `FORBIDDEN_PLACEHOLDER_TOKENS` (5 items in `app/core/schemas.py`)

## Style
- No linter/formatter — only `python -m compileall` syntax check
- Use `from __future__ import annotations` (convention in ~75% of existing modules)
- Structured logging: `logger.info("dotted.event", extra={"event": "dotted.event", ...})`
- Config is a frozen dataclass (`app/core/config.py`), NOT Pydantic BaseSettings
- SDR identity hardcoded in `config/sdr_profile.py`, not env-configurable

## Testing
- `isolated_session_factory` fixture ONLY patches `db_handler.get_db_session` — other imports of `get_db_session` are NOT patched
- No shared LLM mock fixture — mock `call_llm()` per test
- `pytest.ini` sets `pythonpath = .` — no sys.path hacks needed in tests
