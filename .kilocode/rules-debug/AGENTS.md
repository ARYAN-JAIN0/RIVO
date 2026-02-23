# Debug Mode Rules

## LLM Issues
- LLM client connects to Ollama (check `OLLAMA_GENERATE_URL` env var, default: `http://localhost:11434/api/generate`)
- Check `OLLAMA_MODEL` env var (default: `qwen2.5:7b` in [`app/core/config.py`](app/core/config.py))
- Client has built-in retry with fast-fail for local connection errors
- Returns empty string on failure - check logs for "llm.call.unavailable" events
- Rate limiting enforced via `LLM_MIN_INTERVAL_SECONDS` (default: 0.25s)

## Database Connection Issues
- Check `DATABASE_URL` in `.env` (PostgreSQL or SQLite fallback)
- When `DB_CONNECTIVITY_REQUIRED=false` (default in development), system auto-falls back to SQLite
- Session management uses context manager pattern via `get_db_session()`
- Enable `DEBUG=true` in `.env` to see SQL query logging
- Check [`_fallback_to_sqlite_if_optional()`](app/database/db.py:103) for fallback behavior

## Email Validation Failures
Emails fail [`validate_structure()`](app/utils/validators.py:39) if:
- Missing greeting prefix ("hi ", "hello ", "dear ")
- Missing sign-off ("best,", "regards,", etc.) or email address at end
- Less than 30 words
- Contains forbidden tokens like "[your name]", "{company}", "[payment link]"

## Test Database
Tests use isolated SQLite databases in `.test_tmp/` directory via `isolated_session_factory` fixture in [`tests/conftest.py`](tests/conftest.py).

## Logging
- Logs written to `rivo.log` (configurable via `LOG_FILE`)
- Log level via `LOG_LEVEL` env var (default: INFO)
- Structured logging with "event" field for filtering (e.g., "orchestrator.agent.failure")

## Celery Task Issues
- When Celery is not installed, mock implementation runs tasks synchronously
- Set `CELERY_TASK_ALWAYS_EAGER=true` for local synchronous execution
- Check `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` (default: redis://localhost:6379/0)

## SDR Agent Not Processing Leads
Check [`check_negative_gate()`](app/agents/sdr_agent.py:45) which rejects:
- Leads with "layoff" or "competitor" in negative_signals
- Forbidden sectors: government, academic, education, non-profit, ngo
- Leads contacted within 30 days

## Review Queue Issues
- [`save_draft()`](app/database/db_handler.py:94) does NOT advance lead status
- Only [`mark_review_decision()`](app/database/db_handler.py) can move leads to Contacted
- Check `REVIEW_QUEUE_THRESHOLD` (85) and `SIGNAL_THRESHOLD` (60) in [`app/agents/sdr_agent.py`](app/agents/sdr_agent.py)
