"""Queue task wrappers for agent and pipeline execution."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from time import sleep
from typing import Any

from app.services.run_service import RunService
from app.tasks.celery_app import celery_app
from app.tasks.hooks import after_task, before_task
from app.tasks.registry import default_registry
from app.utils.ids import new_run_id

logger = logging.getLogger(__name__)

run_service = RunService()
dead_letter_queue: list[dict[str, Any]] = []


def execute_registered_task(
    task_key: str,
    tenant_id: int,
    user_id: int,
    payload: dict[str, Any] | None = None,
    max_retries: int = 3,
    base_backoff_seconds: float = 1.0,
) -> dict[str, Any]:
    """Execute a registered task with retry metadata and dead-letter handling."""
    payload = payload or {}
    run_id = str(payload.get("run_id") or new_run_id())
    run_service.register(run_id=run_id, agent_name=task_key, status="queued")
    context = {
        "run_id": run_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "trace_id": payload.get("trace_id"),
    }
    logger.info("task.start", extra=before_task(task_key=task_key, context=context))

    try:
        executor = default_registry.get(task_key)
    except KeyError as exc:
        run_service.update_status(
            run_id=run_id,
            status="failed",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error_payload={"error": str(exc)},
        )
        dead_letter_queue.append({"run_id": run_id, "task_key": task_key, "error": str(exc)})
        logger.error("task.registry_key_missing", extra={"event": "task.registry_key_missing", "task_key": task_key, "run_id": run_id})
        return {"run_id": run_id, "status": "failed", "error": str(exc), "dead_lettered": True}

    for attempt in range(max_retries + 1):
        run_service.update_status(run_id=run_id, status="running", retry_count=attempt)
        try:
            executor()
            finished_at = datetime.now(timezone.utc).isoformat()
            run_service.update_status(run_id=run_id, status="succeeded", finished_at=finished_at, retry_count=attempt)
            logger.info("task.finish", extra=after_task(task_key=task_key, context=context, status="succeeded"))
            return {"run_id": run_id, "status": "succeeded", "retry_count": attempt}
        except Exception as exc:  # pragma: no cover - exercised in integration.
            if attempt >= max_retries:
                error_payload = {"error": str(exc), "attempt": attempt}
                finished_at = datetime.now(timezone.utc).isoformat()
                run_service.update_status(
                    run_id=run_id,
                    status="failed",
                    retry_count=attempt,
                    finished_at=finished_at,
                    error_payload=error_payload,
                )
                dead_letter_queue.append({"run_id": run_id, "task_key": task_key, **error_payload})
                logger.exception(
                    "task.failed",
                    extra={"event": "task.failed", "task_key": task_key, "run_id": run_id, "attempt": attempt},
                )
                return {"run_id": run_id, "status": "failed", "retry_count": attempt, "error": str(exc), "dead_lettered": True}
            sleep(base_backoff_seconds * (2**attempt))

    return {"run_id": run_id, "status": "failed", "error": "unreachable"}  # pragma: no cover


@celery_app.task(name="agents.execute")
def execute_agent_task(
    task_key: str,
    tenant_id: int = 1,
    user_id: int = 1,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Celery task entrypoint for single task-key execution."""
    return execute_registered_task(task_key=task_key, tenant_id=tenant_id, user_id=user_id, payload=payload)


@celery_app.task(name="agents.pipeline.run")
def execute_pipeline_task(
    tenant_id: int = 1,
    user_id: int = 1,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Celery task entrypoint for full pipeline execution."""
    return execute_registered_task(task_key="agents.pipeline", tenant_id=tenant_id, user_id=user_id, payload=payload)
