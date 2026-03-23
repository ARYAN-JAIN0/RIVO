# Ask Mode Rules (Non-Obvious Only)

## Misleading Code Organization
- `app/models/` package exists but is NOT the active ORM layer — `app/database/models.py` is the real one (different Base class)
- `app/models/enums.py` exists but is NOT used — `app/core/enums.py` is the active enum source
- `app/core/logging.py` is NOT the logging config — it's helpers. Config is `app/core/logging_config.py`
- `app/core/config.py` uses frozen dataclass, NOT Pydantic BaseSettings despite Pydantic being a dependency
- `app/api/_compat.py` provides full FastAPI mock — code can import without FastAPI installed

## Architecture Context
- Pipeline: SDR → Sales → Negotiation → Finance (status-driven, see `app/orchestrator.py`)
- `app/database/db_handler.py` (23KB) is the main data access layer — not the services
- `save_draft()` does NOT change lead status — only `mark_review_decision()` advances leads
- Two Streamlit dashboards: `app/crm_dashboard.py` and `app/multi_agent_dashboard.py`
- Hand-rolled JWT in `app/auth/jwt.py` (no PyJWT) with HS256

## Key Thresholds (hardcoded, not configurable)
- SDR review queue: score ≥ 85, signal threshold: ≥ 60
- Negotiation approval: confidence ≥ 85, max 3 turns
- Finance dunning approval: confidence ≥ 85

## Environment Behavior
- `DB_CONNECTIVITY_REQUIRED` defaults True in production, False otherwise
- SDR identity hardcoded in `config/sdr_profile.py` (not env-var configurable)
- `get_config()` is `@lru_cache(maxsize=8)` keyed by env parameter — no cache clearing
