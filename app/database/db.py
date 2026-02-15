"""Database connection and session management."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.core.config import get_config

logger = logging.getLogger(__name__)

config = get_config()
DATABASE_URL = config.DATABASE_URL
FALLBACK_SQLITE_URL = "sqlite:///./rivo.db"


def _build_engine(database_url: str):
    return create_engine(
        database_url,
        echo=config.DEBUG,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=10,
        max_overflow=20,
    )


def _configure_engine(database_url: str) -> None:
    global DATABASE_URL, engine, SessionLocal
    DATABASE_URL = database_url
    engine = _build_engine(database_url)
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )


_configure_engine(DATABASE_URL)

Base = declarative_base()


def get_engine():
    """Return the active SQLAlchemy engine."""
    return engine


def get_active_database_url() -> str:
    """Return the currently bound database URL (after fallback, if any)."""
    return DATABASE_URL


def reset_engine(database_url: str | None = None) -> None:
    """Rebind engine/sessionmaker to the given URL (or current active URL)."""
    _configure_engine(database_url or DATABASE_URL)


def get_db() -> Generator[Session, None, None]:
    """Yield a session for dependency injection contexts."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context-manager wrapper for safe DB session lifecycle."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_database_connection() -> bool:
    """Verify DB connectivity during startup."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover - exercised in deployment.
        if config.DB_CONNECTIVITY_REQUIRED:
            logger.exception("database.connection_failed", extra={"event": "database.connection_failed"})
            logger.error("database.connection_failed.details: %s", exc)
            return False
        logger.warning(
            "database.connection_failed.optional",
            extra={"event": "database.connection_failed.optional"},
        )
        if _fallback_to_sqlite_if_optional(exc):
            return True
        logger.error("database.connection_failed.details: %s", exc)
        return False


def _fallback_to_sqlite_if_optional(original_exc: Exception) -> bool:
    """Fallback to SQLite in non-required connectivity mode to keep local runs usable."""
    if config.DB_CONNECTIVITY_REQUIRED or DATABASE_URL.startswith("sqlite"):
        return False

    original_url = DATABASE_URL
    _configure_engine(FALLBACK_SQLITE_URL)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as fallback_exc:  # pragma: no cover - deployment edge case.
        # Restore original engine if fallback itself fails.
        _configure_engine(original_url)
        logger.error("database.connection_failed.details: %s", original_exc)
        logger.error("database.connection_fallback.failed: %s", fallback_exc)
        return False

    logger.warning(
        "database.connection_fallback.sqlite",
        extra={
            "event": "database.connection_fallback.sqlite",
            "from_scheme": original_url.split("://", 1)[0],
            "to_scheme": "sqlite",
        },
    )
    logger.warning("database.connection_failed.details: %s", original_exc)
    return True
