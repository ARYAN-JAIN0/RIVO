from __future__ import annotations

from datetime import datetime

from app.api._compat import APIRouter, Header, HTTPException, Query, RedirectResponse, Response, status
from app.api.v1._authz import authorize, map_auth_error
from app.database.db import get_db_session
from app.database.models import AgentRun, EmailLog, Lead
from app.orchestrator import RevoOrchestrator
from app.services.lead_acquisition_service import LeadAcquisitionService
from app.tasks.agent_tasks import execute_agent_task, run_pipeline_task

router = APIRouter()

TRACKING_PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00"
    b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def _authorize(authorization: str | None, scopes: list[str]):
    try:
        return authorize(authorization=authorization, scopes=scopes)
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc


@router.get("/health")
def health() -> dict:
    return RevoOrchestrator().get_system_health()


@router.post("/lead-acquisition")
def run_lead_acquisition(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=["agents.sdr.run"])
    return LeadAcquisitionService().acquire_and_persist(tenant_id=user.tenant_id)


@router.post("/agents/{agent_name}/run")
def run_agent(agent_name: str, authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=[f"agents.{agent_name}.run"])
    if agent_name not in {"sdr", "sales", "negotiation", "finance"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported agent")
    task = execute_agent_task.delay(agent_name=agent_name, tenant_id=user.tenant_id, user_id=user.user_id)
    return {"status": "queued", "task_id": task.id}


@router.post("/pipeline/run")
def run_full_pipeline(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=["agents.pipeline.run"])
    task = run_pipeline_task.delay(tenant_id=user.tenant_id, user_id=user.user_id)
    return {"status": "queued", "task_id": task.id}


@router.get("/agent-runs")
def list_agent_runs(
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    user = _authorize(authorization, scopes=["runs.read"])
    with get_db_session() as session:
        rows = (
            session.query(AgentRun)
            .filter(AgentRun.tenant_id == user.tenant_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
            .all()
        )

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
def get_agent_run(run_id: int, authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=["runs.read"])
    with get_db_session() as session:
        row = (
            session.query(AgentRun)
            .filter(AgentRun.id == run_id, AgentRun.tenant_id == user.tenant_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
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
def rerun_agent(run_id: int, authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=["runs.retry"])
    with get_db_session() as session:
        row = (
            session.query(AgentRun)
            .filter(AgentRun.id == run_id, AgentRun.tenant_id == user.tenant_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        task = execute_agent_task.delay(agent_name=row.agent_name, tenant_id=user.tenant_id, user_id=user.user_id)
        return {"status": "queued", "task_id": task.id, "agent_name": row.agent_name}


@router.get("/email-logs")
def list_email_logs(
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> list[dict]:
    user = _authorize(authorization, scopes=["logs.read"])
    with get_db_session() as session:
        rows = (
            session.query(EmailLog)
            .filter(EmailLog.tenant_id == user.tenant_id)
            .order_by(EmailLog.created_at.desc())
            .limit(limit)
            .all()
        )
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
def list_leads(
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> list[dict]:
    user = _authorize(authorization, scopes=["runs.read"])
    with get_db_session() as session:
        leads = (
            session.query(Lead)
            .filter(Lead.tenant_id == user.tenant_id)
            .order_by(Lead.created_at.desc())
            .limit(limit)
            .all()
        )
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
def track_open(tracking_id: str) -> Response:
    with get_db_session() as session:
        row = session.query(EmailLog).filter(EmailLog.tracking_id == tracking_id).first()
        if row:
            row.opened_at = datetime.utcnow()
            session.commit()
    return Response(content=TRACKING_PIXEL_GIF, media_type="image/gif", status_code=status.HTTP_200_OK)


@router.get("/track/click/{tracking_id}")
def track_click(
    tracking_id: str,
    redirect_to: str = Query(default="https://example.com"),
) -> RedirectResponse:
    with get_db_session() as session:
        row = session.query(EmailLog).filter(EmailLog.tracking_id == tracking_id).first()
        if row:
            row.clicked_at = datetime.utcnow()
            session.commit()
    return RedirectResponse(url=redirect_to, status_code=status.HTTP_302_FOUND)


@router.post("/track/reply/{lead_id}")
def track_reply(lead_id: int, authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=["logs.read"])
    with get_db_session() as session:
        lead = session.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == user.tenant_id).first()
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead not found")
        lead.last_reply_at = datetime.utcnow()
        lead.next_followup_at = None
        session.commit()
    return {"status": "ok", "lead_id": lead_id}
