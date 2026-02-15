"""Startup validation and bootstrap helpers."""

from __future__ import annotations

import logging

from app.core.config import get_config
from app.core.logging_config import configure_logging
from app.database.db import get_active_database_url, verify_database_connection

logger = logging.getLogger(__name__)


def validate_startup_config() -> None:
    """Fail-fast config and connectivity checks."""
    config = get_config()
    database_ok = verify_database_connection()
    active_database_url = get_active_database_url()
    if not database_ok and config.DB_CONNECTIVITY_REQUIRED:
        raise RuntimeError("Database connectivity check failed.")
    if not database_ok:
        logger.warning(
            "startup.database.connectivity_optional_failed",
            extra={"event": "startup.database.connectivity_optional_failed"},
        )

    if config.is_production and active_database_url.startswith("sqlite"):
        logger.warning(
            "startup.production.sqlite_detected",
            extra={"event": "startup.production.sqlite_detected"},
        )

    logger.info(
        "startup.config.validated",
        extra={
            "event": "startup.config.validated",
            "env": config.ENV,
            "database_url_scheme": active_database_url.split("://", 1)[0],
            "db_connectivity_required": config.DB_CONNECTIVITY_REQUIRED,
        },
    )


def bootstrap() -> None:
    """Initialize logging and validate runtime configuration."""
    configure_logging()
    validate_startup_config()
