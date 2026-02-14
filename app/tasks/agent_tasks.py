from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.enums import LeadStatus
from app.database.db import get_db_session
from app.database.models import AgentRun, Lead
from app.services.email_service import EmailService
from app.services.run_service import RunService
from app.tasks.celery_app import celery_app
from app.tasks.hooks import after_task, before_task
from app.tasks.registry import default_registry

logger = logging.getLogger(__name__)

# Phase 1/2 compatibility layer: these symbols are consumed by API modules and
# queue integration tests.
run_service = RunService()
dead_letter_queue: list[dict[str, Any]] = []

AGENT_TASK_KEYS = {
    "sdr": "agents.sdr",
    "sales": "agents.sales",
    "negotiation": "agents.negotiation",
    "finance": "agents.finance",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serialize_error(exc: Exception) -> dict[str, str]:
    return {
        "type": exc.__class__.__name__,
        "message": str(exc),
    }


def execute_registered_task(
    task_key: str,
    tenant_id: int,
    user_id: int,
    payload: dict[str, Any] | None = None,
    max_retries: int = 2,
    base_backoff_seconds: float = 0.25,
) -> dict[str, Any]:
    """Execute a registered task with retry bookkeeping and dead-letter capture."""
    run_id = f"run-{uuid.uuid4().hex}"
    run_service.register(run_id=run_id, agent_name=task_key, status="queued")
    context = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "run_id": run_id,
        "trace_id": uuid.uuid4().hex,
        "payload": payload or {},
    }
    logger.info("task.start", extra=before_task(task_key=task_key, context=context))

    attempt_used = 0
    last_error: dict[str, str] | None = None

    for attempt in range(max_retries + 1):
        attempt_used = attempt
        run_service.update_status(run_id=run_id, status="running", retry_count=attempt)
        try:
            executor = default_registry.get(task_key)
            executor()
            finished_at = datetime.now(timezone.utc).isoformat()
            run_service.update_status(
                run_id=run_id,
                status="succeeded",
                retry_count=attempt,
                finished_at=finished_at,
            )
            logger.info("task.finish", extra=after_task(task_key=task_key, context=context, status="succeeded"))
            return {
                "run_id": run_id,
                "status": "succeeded",
                "retry_count": attempt,
                "dead_lettered": False,
            }
        except KeyError as exc:
            last_error = _serialize_error(exc)
            break
        except Exception as exc:
            last_error = _serialize_error(exc)
            if attempt < max_retries:
                delay = max(0.0, base_backoff_seconds) * (2**attempt)
                if delay > 0:
                    time.sleep(delay)
                continue
            break

    finished_at = datetime.now(timezone.utc).isoformat()
    run_service.update_status(
        run_id=run_id,
        status="failed",
        retry_count=attempt_used,
        finished_at=finished_at,
        error_payload=last_error,
    )
    dead_entry = {
        "run_id": run_id,
        "task_key": task_key,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "retry_count": attempt_used,
        "error_payload": last_error or {"message": "unknown error"},
        "failed_at": finished_at,
    }
    dead_letter_queue.append(dead_entry)
    logger.error("task.failed", extra=after_task(task_key=task_key, context=context, status="failed"))
    return {
        "run_id": run_id,
        "status": "failed",
        "retry_count": attempt_used,
        "dead_lettered": True,
        "error_payload": last_error,
    }


def _create_run(agent_name: str, tenant_id: int, task_id: str | None = None) -> int:
    with get_db_session() as session:
        row = AgentRun(agent_name=agent_name, tenant_id=tenant_id, task_id=task_id, status="queued")
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def _update_run(run_id: int, **fields: Any) -> None:
    with get_db_session() as session:
        row = session.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not row:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        session.commit()


@celery_app.task(bind=True, name="agents.execute")
def execute_agent_task(
    self,
    agent_name: str,
    tenant_id: int = 1,
    user_id: int = 1,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_id = _create_run(agent_name=agent_name, tenant_id=tenant_id, task_id=getattr(self.request, "id", None))
    started = time.time()
    _update_run(run_id, status="running", started_at=_now_utc())

    task_key = AGENT_TASK_KEYS.get(agent_name)
    if task_key is None:
        _update_run(run_id, status="failed", error_message=f"unknown agent {agent_name}", finished_at=_now_utc())
        return {"run_id": run_id, "status": "failed", "error": "unknown agent"}

    try:
        result = execute_registered_task(
            task_key=task_key,
            tenant_id=tenant_id,
            user_id=user_id,
            payload=payload,
        )
        duration_ms = int((time.time() - started) * 1000)
        if result["status"] == "succeeded":
            _update_run(run_id, status="success", finished_at=_now_utc(), duration_ms=duration_ms)
            return {
                "run_id": run_id,
                "status": "success",
                "duration_ms": duration_ms,
                "retry_count": result["retry_count"],
            }

        error_message = (result.get("error_payload") or {}).get("message", "task failed")
        _update_run(
            run_id,
            status="failed",
            finished_at=_now_utc(),
            duration_ms=duration_ms,
            error_message=error_message,
        )
        return {
            "run_id": run_id,
            "status": "failed",
            "duration_ms": duration_ms,
            "retry_count": result["retry_count"],
            "error": error_message,
        }
    except Exception as exc:
        duration_ms = int((time.time() - started) * 1000)
        _update_run(run_id, status="failed", finished_at=_now_utc(), duration_ms=duration_ms, error_message=str(exc))
        logger.exception("agent_task.failed", extra={"event": "agent_task.failed", "agent_name": agent_name, "run_id": run_id})
        raise


@celery_app.task(name="agents.run_pipeline")
def run_pipeline_task(tenant_id: int = 1, user_id: int = 1) -> dict[str, Any]:
    tasks: dict[str, str] = {}
    for agent_name in ["sdr", "sales", "negotiation", "finance"]:
        result = execute_agent_task.delay(agent_name=agent_name, tenant_id=tenant_id, user_id=user_id)
        tasks[agent_name] = result.id
    return {"status": "queued", "tasks": tasks}


def _followup_day_for_attempt(attempt_index: int, cadence_days: list[int]) -> int:
    capped = min(attempt_index, len(cadence_days) - 1)
    return cadence_days[capped]


@celery_app.task(name="agents.followup")
def followup_scheduler_task(tenant_id: int = 1, max_attempts: int = 3) -> dict[str, int | str]:
    """Send follow-ups only when lead.next_followup_at is due.

    Cadence labels are day 3 / 7 / 14 for attempts 1..3.
    """
    email_service = EmailService()
    cadence_days = [3, 7, 14]
    now = _now_utc()
    sent = 0
    eligible = 0
    scheduled = 0

    with get_db_session() as session:
        leads = (
            session.query(Lead)
            .filter(Lead.tenant_id == tenant_id)
            .filter(Lead.status == LeadStatus.CONTACTED.value)
            .filter(Lead.last_reply_at.is_(None))
            .all()
        )

        for lead in leads:
            current = int(lead.followup_count or 0)
            if current >= max_attempts:
                continue

            due_at = lead.next_followup_at
            if due_at is None:
                anchor = lead.last_contacted or now
                due_at = anchor + timedelta(days=_followup_day_for_attempt(current, cadence_days))
                lead.next_followup_at = due_at
                scheduled += 1

            if due_at > now:
                continue

            eligible += 1
            day_label = _followup_day_for_attempt(current, cadence_days)
            if email_service.send_followup(lead, day=day_label):
                sent += 1
                lead.followup_count = current + 1
                if lead.followup_count >= max_attempts:
                    lead.next_followup_at = None
                else:
                    next_gap = _followup_day_for_attempt(lead.followup_count, cadence_days)
                    lead.next_followup_at = now + timedelta(days=next_gap)
        session.commit()

    return {"status": "ok", "sent": sent, "eligible": eligible, "scheduled": scheduled}
