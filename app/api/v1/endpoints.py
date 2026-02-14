from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.database.db import get_db_session
from sqlalchemy import func

from app.database.models import AgentRun, Deal, EmailLog, Lead
from app.services.sales_intelligence_service import SalesIntelligenceService
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


@router.post("/sales/deals/{deal_id}/manual-override")
def sales_manual_override(deal_id: int, new_stage: str, reason: str = "manual override") -> dict:
    ok = SalesIntelligenceService().transition_stage(deal_id, new_stage, actor="manual", reason=reason)
    if not ok:
        raise HTTPException(status_code=400, detail="invalid stage transition")
    return {"status": "ok", "deal_id": deal_id, "new_stage": new_stage}


@router.post("/sales/deals/{deal_id}/rescore")
def sales_rescore(deal_id: int) -> dict:
    ok = SalesIntelligenceService().rescore_deal(deal_id, actor="manual")
    if not ok:
        raise HTTPException(status_code=404, detail="deal not found")
    return {"status": "ok", "deal_id": deal_id}


@router.get("/analytics/pipeline")
def analytics_pipeline() -> dict:
    with get_db_session() as session:
        rows = (
            session.query(Deal.stage, func.count(Deal.id).label("count"), func.sum(Deal.deal_value).label("value"))
            .group_by(Deal.stage)
            .all()
        )
    return {
        "stages": [
            {"stage": stage, "count": int(count or 0), "value": int(value or 0)}
            for stage, count, value in rows
        ]
    }


@router.get("/analytics/forecast")
def analytics_forecast() -> dict:
    with get_db_session() as session:
        deals = session.query(Deal).filter(Deal.status != "Closed").all()

    weighted = sum((float(d.deal_value or 0) * float(d.probability or 0) / 100.0) for d in deals)
    pipeline = sum(float(d.deal_value or 0) for d in deals)
    monthly: dict[str, float] = {}
    for d in deals:
        month = d.forecast_month or "unknown"
        monthly[month] = monthly.get(month, 0.0) + (float(d.deal_value or 0) * float(d.probability or 0) / 100.0)

    confidence = round(sum(float(d.probability_confidence or 50) for d in deals) / max(len(deals), 1), 2)
    return {
        "formula": "sum(deal_value * probability/100)",
        "pipeline_value": round(pipeline, 2),
        "weighted_revenue_projection": round(weighted, 2),
        "monthly_forecast": {k: round(v, 2) for k, v in monthly.items()},
        "forecast_confidence": confidence,
    }


@router.get("/analytics/revenue")
def analytics_revenue() -> dict:
    with get_db_session() as session:
        won = session.query(Deal).filter(Deal.stage == "Closed Won").all()
        open_deals = session.query(Deal).filter(Deal.status != "Closed").all()
    realized = sum(float(d.deal_value or 0) for d in won)
    projected = sum(float(d.deal_value or 0) * float(d.probability or 0) / 100.0 for d in open_deals)
    return {"realized_revenue": round(realized, 2), "projected_revenue": round(projected, 2)}


@router.get("/analytics/segmentation")
def analytics_segmentation() -> dict:
    with get_db_session() as session:
        rows = session.query(Deal.segment_tag, func.count(Deal.id)).group_by(Deal.segment_tag).all()
    return {"segments": [{"tag": tag or "Unknown", "count": int(count)} for tag, count in rows]}


@router.get("/analytics/probability-breakdown")
def analytics_probability_breakdown(limit: int = 100) -> dict:
    with get_db_session() as session:
        deals = session.query(Deal).order_by(Deal.last_updated.desc()).limit(limit).all()
    return {
        "items": [
            {
                "deal_id": d.id,
                "company": d.company,
                "stage": d.stage,
                "probability": d.probability,
                "confidence": d.probability_confidence,
                "breakdown": d.probability_breakdown,
                "explanation": d.probability_explanation,
            }
            for d in deals
        ]
    }
