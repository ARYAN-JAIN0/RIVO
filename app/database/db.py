"""Database connection and session management."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.core.config import get_config

logger = logging.getLogger(__name__)

config = get_config()
DATABASE_URL = config.DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    echo=config.DEBUG,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


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
        else:
            logger.warning(
                "database.connection_failed.optional",
                extra={"event": "database.connection_failed.optional"},
            )
        logger.error("database.connection_failed.details: %s", exc)
        return False
