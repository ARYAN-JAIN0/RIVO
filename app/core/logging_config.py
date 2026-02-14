"""Centralized structured logging configuration."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_config


class JsonFormatter(logging.Formatter):
    """Emit logs as structured JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "event"):
            payload["event"] = getattr(record, "event")
        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    """Configure app-wide logging once."""
    config = get_config()
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    formatter = JsonFormatter()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if config.LOG_FILE:
        file_handler = logging.FileHandler(config.LOG_FILE)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Avoid noisy SQL in production-like mode even if libraries emit debug logs.
    if config.is_production:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

