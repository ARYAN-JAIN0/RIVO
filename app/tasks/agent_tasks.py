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
