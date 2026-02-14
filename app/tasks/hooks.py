"""Lifecycle hooks for queue task execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.logging import LogContext, build_log_event


def before_task(task_key: str, context: dict[str, Any]) -> dict[str, Any]:
    """Build pre-task log payload."""
    return build_log_event(
        event="task.start",
        context=LogContext(
            tenant_id=str(context.get("tenant_id")) if context.get("tenant_id") is not None else None,
            user_id=str(context.get("user_id")) if context.get("user_id") is not None else None,
            run_id=context.get("run_id"),
            agent_name=task_key,
            trace_id=context.get("trace_id"),
        ),
    )


def after_task(task_key: str, context: dict[str, Any], status: str) -> dict[str, Any]:
    """Build post-task log payload."""
    return build_log_event(
        event="task.finish",
        context=LogContext(
            tenant_id=str(context.get("tenant_id")) if context.get("tenant_id") is not None else None,
            user_id=str(context.get("user_id")) if context.get("user_id") is not None else None,
            run_id=context.get("run_id"),
            agent_name=task_key,
            trace_id=context.get("trace_id"),
        ),
        status=status,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
