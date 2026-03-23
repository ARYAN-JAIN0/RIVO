# Architect Mode Rules (Non-Obvious Only)

## Dual System Warning
- Two ORM model systems with DIFFERENT Base classes: `app/database/models.py` (active, Alembic-managed) vs `app/models/` (planned refactor, disconnected). Any migration or schema work must target `app/database/models.py` only.
- Two enum systems: `app/core/enums.py` (active, plain Enum) vs `app/models/enums.py` (inactive, str+Enum with extra values like `Void`, `RunStatus`, `UserRole`). Consolidation needed.

## Hidden Coupling
- `isolated_session_factory` test fixture only patches `db_handler.get_db_session` — any new service that imports `get_db_session` directly from `app.database.db` will bypass test isolation
- `FORBIDDEN_TOKENS` (validators.py, 8 items) vs `FORBIDDEN_PLACEHOLDER_TOKENS` (schemas.py, 5 items) — validation inconsistency between structural check and Pydantic schema
- `app/api/_compat.py` mock layer means API modules can't use FastAPI features not covered by the mock
- Eight files have `sys.path.insert(0, PROJECT_ROOT)` — prevents clean package refactoring

## Architectural Constraints
- Config is frozen dataclass with `@lru_cache(maxsize=8)` — no runtime config changes, no cache invalidation
- `get_db_session()` does NOT auto-commit — all write paths must explicitly commit
- Auth bypass: `get_current_user(token=None)` returns admin — script-mode execution has full permissions
- Middleware LIFO order: CorrelationID must be added AFTER RateLimit to execute first
- Alembic resolves DATABASE_URL at import time — cannot dynamically switch databases

## Database
- docker-compose: postgres:14, CI: postgres:16 — migrations must be compatible with both
- SQLite fallback in non-production silently ignores pool parameters
- `alembic_version` table may be missing on pre-migration databases — `init_db.py` handles baseline stamping to `20260213_0001`
- All unique constraints are tenant-scoped (e.g., `uq_leads_tenant_email`)

## No Code Quality Tooling
- No ruff, pylint, mypy, black, or isort configured — only `python -m compileall` syntax check in CI
- RBAC uses 5 roles with `domain.resource.action` scope strings; admin gets wildcard `*`
