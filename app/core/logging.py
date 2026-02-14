"""Structured logging helpers for FastAPI-era backend."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class LogContext:
    """Normalized context fields expected in structured logs."""

    tenant_id: str | None = None
    user_id: str | None = None
    run_id: str | None = None
    agent_name: str | None = None
    trace_id: str | None = None


def build_log_event(event: str, context: LogContext, **fields: Any) -> dict[str, Any]:
    """Build a normalized structured log payload."""
    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "tenant_id": context.tenant_id,
        "user_id": context.user_id,
        "run_id": context.run_id,
        "agent_name": context.agent_name,
        "trace_id": context.trace_id,
    }
    payload.update(fields)
    return payload

