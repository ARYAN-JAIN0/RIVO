# Debug Mode Rules (Non-Obvious Only)

## Database Debugging
- `DB_CONNECTIVITY_REQUIRED` defaults to `True` in production, `False` otherwise — not a simple false
- SQLite fallback activates silently when PostgreSQL unavailable and `DB_CONNECTIVITY_REQUIRED=false`
- SQLite ignores pool parameters (`pool_size`, `pool_recycle`, etc.) — connection behavior differs from PostgreSQL
- `get_db_session()` never auto-commits — if data isn't persisting, check for missing `session.commit()`
- Alembic resolves `DATABASE_URL` at import time via `get_config()` — env vars must be set BEFORE running alembic

## Test Debugging
- Test isolation fixture ONLY patches `db_handler.get_db_session` — services using `BaseService(db=None)` or importing `get_db_session` directly from `app.database.db` will hit the real database
- `.test_tmp/` accumulates SQLite files with no automatic cleanup
- CI runs 3 separate pytest invocations (unit, integration, phase2) — failures in one group don't block others
- `get_config("test")` returns a separate cached instance from `get_config()` (no cache clearing mechanism)

## Auth Debugging
- `get_current_user(token=None)` silently returns admin context — unauthenticated paths run as admin
- JWT is hand-rolled (`app/auth/jwt.py`) using hmac+hashlib — no PyJWT library errors to look for
- Password verification has SHA-256 legacy fallback for pre-bcrypt records (pepper format: `{pepper}:{password}`)

## Logging
- Two logging modules: `app/core/logging_config.py` (setup with JsonFormatter) and `app/core/logging.py` (LogContext helpers)
- Structured logs use `extra={"event": "dotted.event.name"}` — filter on the `event` key
- Middleware order is LIFO: CorrelationID runs before RateLimit despite being added after

## Common Silent Failures
- Importing models from `app.models` instead of `app.database.models` — queries return empty, no error
- Importing enums from `app.models.enums` instead of `app.core.enums` — comparisons fail silently
- `call_llm()` returns `""` on failure, not None — `if response` works, `if response is not None` doesn't catch failures
- Docker uses postgres:14, CI uses postgres:16 — migration edge cases possible
