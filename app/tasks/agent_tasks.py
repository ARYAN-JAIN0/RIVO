from __future__ import annotations

import logging
import time
from datetime import datetime

from app.agents.finance_agent import run_finance_agent
from app.agents.negotiation_agent import run_negotiation_agent
from app.agents.sales_agent import run_sales_agent
from app.agents.sdr_agent import run_sdr_agent
from app.database.db import get_db_session
from app.database.models import AgentRun, Lead
from app.services.email_service import EmailService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

AGENTS = {
    "sdr": run_sdr_agent,
    "sales": run_sales_agent,
    "negotiation": run_negotiation_agent,
    "finance": run_finance_agent,
}


def _create_run(agent_name: str, tenant_id: int, task_id: str | None = None) -> int:
    with get_db_session() as session:
        row = AgentRun(agent_name=agent_name, tenant_id=tenant_id, task_id=task_id, status="queued")
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def _update_run(run_id: int, **fields) -> None:
    with get_db_session() as session:
        row = session.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not row:
            return
        for k, v in fields.items():
            setattr(row, k, v)
        session.commit()


@celery_app.task(bind=True, name="agents.execute")
def execute_agent_task(self, agent_name: str, tenant_id: int = 1) -> dict:
    run_id = _create_run(agent_name=agent_name, tenant_id=tenant_id, task_id=self.request.id)
    started = time.time()
    _update_run(run_id, status="running", started_at=datetime.utcnow())

    fn = AGENTS.get(agent_name)
    if fn is None:
        _update_run(run_id, status="failed", error_message=f"unknown agent {agent_name}", finished_at=datetime.utcnow())
        return {"run_id": run_id, "status": "failed", "error": "unknown agent"}

    try:
        fn()
        duration_ms = int((time.time() - started) * 1000)
        _update_run(run_id, status="success", finished_at=datetime.utcnow(), duration_ms=duration_ms)
        return {"run_id": run_id, "status": "success", "duration_ms": duration_ms}
    except Exception as exc:
        duration_ms = int((time.time() - started) * 1000)
        _update_run(run_id, status="failed", finished_at=datetime.utcnow(), duration_ms=duration_ms, error_message=str(exc))
        logger.exception("agent_task.failed", extra={"event": "agent_task.failed", "agent_name": agent_name, "run_id": run_id})
        raise


@celery_app.task(name="agents.run_pipeline")
def run_pipeline_task(tenant_id: int = 1) -> dict:
    results = {}
    for agent_name in ["sdr", "sales", "negotiation", "finance"]:
        result = execute_agent_task.delay(agent_name=agent_name, tenant_id=tenant_id)
        results[agent_name] = result.id
    return {"status": "queued", "tasks": results}


@celery_app.task(name="agents.followup")
def followup_scheduler_task(tenant_id: int = 1, max_attempts: int = 3) -> dict:
    email_service = EmailService()
    day_map = {0: 3, 1: 7, 2: 14}
    sent = 0

    with get_db_session() as session:
        leads = (
            session.query(Lead)
            .filter(Lead.tenant_id == tenant_id)
            .filter(Lead.status == "Contacted")
            .filter((Lead.last_reply_at.is_(None)))
            .all()
        )

        for lead in leads:
            current = int(lead.followup_count or 0)
            if current >= max_attempts:
                continue
            day = day_map.get(current, 14)
            if email_service.send_followup(lead, day=day):
                lead.followup_count = current + 1
                sent += 1
        session.commit()

    return {"status": "ok", "sent": sent}
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
