"""Startup validation and bootstrap helpers."""

from __future__ import annotations

import logging

from app.core.config import get_config
from app.core.logging_config import configure_logging
from app.database.db import verify_database_connection

logger = logging.getLogger(__name__)


def validate_startup_config() -> None:
    """Fail-fast config and connectivity checks."""
    config = get_config()
    if not verify_database_connection():
        raise RuntimeError("Database connectivity check failed.")

    if config.is_production and config.DATABASE_URL.startswith("sqlite"):
        logger.warning(
            "startup.production.sqlite_detected",
            extra={"event": "startup.production.sqlite_detected"},
        )

    logger.info(
        "startup.config.validated",
        extra={
            "event": "startup.config.validated",
            "env": config.ENV,
            "database_url_scheme": config.DATABASE_URL.split("://", 1)[0],
        },
    )


def bootstrap() -> None:
    """Initialize logging and validate runtime configuration."""
    configure_logging()
    validate_startup_config()
