from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.database.db import get_db_session
from app.database.models import AgentRun, EmailLog, Lead
from app.orchestrator import RevoOrchestrator
from app.services.lead_acquisition_service import LeadAcquisitionService
from app.tasks.agent_tasks import execute_agent_task, run_pipeline_task

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return RevoOrchestrator().get_system_health()


@router.post("/lead-acquisition")
def run_lead_acquisition(tenant_id: int = 1) -> dict:
    return LeadAcquisitionService().acquire_and_persist(tenant_id=tenant_id)


@router.post("/agents/{agent_name}/run")
def run_agent(agent_name: str, tenant_id: int = 1) -> dict:
    if agent_name not in {"sdr", "sales", "negotiation", "finance"}:
        raise HTTPException(status_code=400, detail="unsupported agent")
    task = execute_agent_task.delay(agent_name=agent_name, tenant_id=tenant_id)
    return {"status": "queued", "task_id": task.id}


@router.post("/pipeline/run")
def run_full_pipeline(tenant_id: int = 1) -> dict:
    task = run_pipeline_task.delay(tenant_id=tenant_id)
    return {"status": "queued", "task_id": task.id}


@router.get("/agent-runs")
def list_agent_runs(limit: int = 100) -> dict:
    with get_db_session() as session:
        rows = session.query(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit).all()

    success = sum(1 for row in rows if row.status == "success")
    failed = sum(1 for row in rows if row.status == "failed")
    ratio = round((success / max(success + failed, 1)) * 100.0, 2)

    return {
        "items": [
            {
                "id": row.id,
                "agent_name": row.agent_name,
                "status": row.status,
                "duration_ms": row.duration_ms,
                "error_message": row.error_message,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "metrics": {
            "success": success,
            "failed": failed,
            "success_ratio_percent": ratio,
        },
    }


@router.get("/agent-runs/{run_id}")
def get_agent_run(run_id: int) -> dict:
    with get_db_session() as session:
        row = session.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="run not found")
        return {
            "id": row.id,
            "agent_name": row.agent_name,
            "status": row.status,
            "task_id": row.task_id,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "duration_ms": row.duration_ms,
            "error_message": row.error_message,
            "created_at": row.created_at,
        }


@router.post("/agent-runs/{run_id}/rerun")
def rerun_agent(run_id: int, tenant_id: int = 1) -> dict:
    with get_db_session() as session:
        row = session.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="run not found")
        task = execute_agent_task.delay(agent_name=row.agent_name, tenant_id=tenant_id)
        return {"status": "queued", "task_id": task.id, "agent_name": row.agent_name}


@router.get("/email-logs")
def list_email_logs(limit: int = 100) -> list[dict]:
    with get_db_session() as session:
        rows = session.query(EmailLog).order_by(EmailLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "lead_id": row.lead_id,
            "recipient_email": row.recipient_email,
            "subject": row.subject,
            "status": row.status,
            "opened_at": row.opened_at,
            "clicked_at": row.clicked_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/leads")
def list_leads(limit: int = 100) -> list[dict]:
    with get_db_session() as session:
        leads = session.query(Lead).order_by(Lead.created_at.desc()).limit(limit).all()
    return [
        {
            "id": lead.id,
            "name": lead.name,
            "email": lead.email,
            "company": lead.company,
            "industry": lead.industry,
            "website": lead.website,
            "location": lead.location,
            "status": lead.status,
            "review_status": lead.review_status,
            "followup_count": lead.followup_count,
            "created_at": lead.created_at,
        }
        for lead in leads
    ]


@router.get("/track/open/{tracking_id}")
def track_open(tracking_id: str) -> dict:
    with get_db_session() as session:
        row = session.query(EmailLog).filter(EmailLog.tracking_id == tracking_id).first()
        if row:
            row.opened_at = datetime.utcnow()
            session.commit()
    return {"status": "ok"}
