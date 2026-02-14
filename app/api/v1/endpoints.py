from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean

from pydantic import BaseModel, Field

from app.api._compat import APIRouter, Header, HTTPException, Query, RedirectResponse, Response, status
from app.api.v1._authz import authorize, map_auth_error
from app.database.db import get_db_session
from app.database.models import AgentRun, Deal, EmailLog, Lead
from app.orchestrator import RevoOrchestrator
from app.services.lead_acquisition_service import LeadAcquisitionService
from app.services.sales_intelligence_service import PIPELINE_STAGES, SalesIntelligenceService
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


class DealManualOverrideRequest(BaseModel):
    stage: str | None = Field(default=None, max_length=40)
    probability: float | None = Field(default=None, ge=0.0, le=100.0)
    deal_value: int | None = Field(default=None, ge=0)
    cost_estimate: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default="", max_length=2000)


def _safe_float(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _safe_int(value: float | int | None) -> int:
    if value is None:
        return 0
    return int(value)


def _weighted_value(deal: Deal) -> float:
    return round(_safe_float(deal.deal_value) * (_safe_float(deal.probability) / 100.0), 2)


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


@router.post("/sales/deals/{deal_id}/rescore")
def rescore_deal(deal_id: int, authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=["agents.sales.run"])
    with get_db_session() as session:
        deal = session.query(Deal).filter(Deal.id == deal_id, Deal.tenant_id == user.tenant_id).first()
        if not deal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="deal not found")

    svc = SalesIntelligenceService()
    if not svc.rescore_deal(deal_id=deal_id, actor=f"user:{user.user_id}"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="deal rescore failed")

    with get_db_session() as session:
        refreshed = session.query(Deal).filter(Deal.id == deal_id, Deal.tenant_id == user.tenant_id).first()
        if not refreshed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="deal not found")
        return {
            "status": "ok",
            "deal_id": refreshed.id,
            "stage": refreshed.stage,
            "probability": refreshed.probability,
            "probability_confidence": refreshed.probability_confidence,
            "segment_tag": refreshed.segment_tag,
            "margin": refreshed.margin,
            "forecast_month": refreshed.forecast_month,
        }


@router.post("/sales/deals/{deal_id}/manual-override")
def manual_override_deal(
    deal_id: int,
    payload: DealManualOverrideRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    user = _authorize(authorization, scopes=["runs.override"])
    if payload.stage and payload.stage not in PIPELINE_STAGES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid stage")

    with get_db_session() as session:
        deal = session.query(Deal).filter(Deal.id == deal_id, Deal.tenant_id == user.tenant_id).first()
        if not deal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="deal not found")

    svc = SalesIntelligenceService()
    if payload.stage:
        moved = svc.transition_stage(
            deal_id=deal_id,
            new_stage=payload.stage,
            actor=f"user:{user.user_id}",
            reason=payload.reason or "manual override",
        )
        if not moved:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="stage transition not allowed")

    with get_db_session() as session:
        deal = session.query(Deal).filter(Deal.id == deal_id, Deal.tenant_id == user.tenant_id).first()
        if not deal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="deal not found")

        if payload.probability is not None:
            deal.probability = round(payload.probability, 2)
        if payload.deal_value is not None:
            deal.deal_value = payload.deal_value
        if payload.cost_estimate is not None:
            deal.cost_estimate = payload.cost_estimate
        if payload.deal_value is not None or payload.cost_estimate is not None:
            margin = svc.calculate_margin(
                deal_value=int(deal.deal_value or 0),
                cost_estimate=int(deal.cost_estimate or 0),
            )
            deal.margin = margin.margin
        if payload.reason:
            deal.notes = (deal.notes or "") + f"\n[manual_override] {payload.reason}"
        deal.last_updated = datetime.utcnow()
        session.commit()
        session.refresh(deal)
        return {
            "status": "ok",
            "deal_id": deal.id,
            "stage": deal.stage,
            "probability": deal.probability,
            "deal_value": deal.deal_value,
            "cost_estimate": deal.cost_estimate,
            "margin": deal.margin,
            "last_updated": deal.last_updated,
        }


def _fetch_tenant_deals(tenant_id: int) -> list[Deal]:
    with get_db_session() as session:
        return session.query(Deal).filter(Deal.tenant_id == tenant_id).all()


@router.get("/analytics/pipeline")
def get_pipeline_analytics(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=["metrics.read"])
    deals = _fetch_tenant_deals(user.tenant_id)
    open_deals = [deal for deal in deals if (deal.status or "Open") != "Closed"]
    closed_deals = [deal for deal in deals if (deal.status or "Open") == "Closed"]

    pipeline_value = round(sum(_safe_float(deal.deal_value) for deal in open_deals), 2)
    weighted_projection = round(sum(_weighted_value(deal) for deal in open_deals), 2)
    low_margin_count = sum(1 for deal in open_deals if _safe_float(deal.margin) < 0.2 and _safe_float(deal.deal_value) > 0)

    by_stage: dict[str, dict[str, float | int]] = defaultdict(lambda: {"count": 0, "pipeline_value": 0.0, "weighted_value": 0.0})
    for deal in open_deals:
        stage = deal.stage or "Unknown"
        by_stage[stage]["count"] += 1
        by_stage[stage]["pipeline_value"] += _safe_float(deal.deal_value)
        by_stage[stage]["weighted_value"] += _weighted_value(deal)

    ordered_stages = [*PIPELINE_STAGES, *sorted(stage for stage in by_stage if stage not in PIPELINE_STAGES)]
    by_stage_rows = [
        {
            "stage": stage,
            "count": int(by_stage[stage]["count"]),
            "pipeline_value": round(float(by_stage[stage]["pipeline_value"]), 2),
            "weighted_value": round(float(by_stage[stage]["weighted_value"]), 2),
        }
        for stage in ordered_stages
        if stage in by_stage
    ]

    return {
        "tenant_id": user.tenant_id,
        "open_deals": len(open_deals),
        "closed_deals": len(closed_deals),
        "pipeline_value": pipeline_value,
        "weighted_revenue_projection": weighted_projection,
        "low_margin_open_deals": low_margin_count,
        "by_stage": by_stage_rows,
    }


@router.get("/analytics/forecast")
def get_forecast_analytics(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=["metrics.read"])
    deals = _fetch_tenant_deals(user.tenant_id)
    open_deals = [deal for deal in deals if (deal.status or "Open") != "Closed"]

    monthly: dict[str, float] = defaultdict(float)
    confidences: list[int] = []
    for deal in open_deals:
        month = deal.forecast_month
        if not month and deal.expected_close_date:
            month = deal.expected_close_date.strftime("%Y-%m")
        month = month or "unscheduled"
        monthly[month] += _weighted_value(deal)
        if deal.probability_confidence is not None:
            confidences.append(int(deal.probability_confidence))

    monthly_rows = [
        {"forecast_month": month, "weighted_revenue": round(value, 2)}
        for month, value in sorted(monthly.items(), key=lambda x: x[0])
    ]
    weighted_projection = round(sum(row["weighted_revenue"] for row in monthly_rows), 2)
    confidence = round(mean(confidences), 2) if confidences else 0.0

    return {
        "tenant_id": user.tenant_id,
        "weighted_revenue_projection": weighted_projection,
        "forecast_confidence": confidence,
        "monthly": monthly_rows,
    }


@router.get("/analytics/revenue")
def get_revenue_analytics(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=["metrics.read"])
    deals = _fetch_tenant_deals(user.tenant_id)

    won = [deal for deal in deals if (deal.stage or "") in {"Closed Won", "Won"}]
    lost = [deal for deal in deals if (deal.stage or "") in {"Closed Lost", "Lost"}]
    open_deals = [deal for deal in deals if deal not in won and deal not in lost]

    booked_revenue = round(sum(_safe_float(deal.deal_value) for deal in won), 2)
    open_pipeline_value = round(sum(_safe_float(deal.deal_value) for deal in open_deals), 2)
    weighted_projection = round(sum(_weighted_value(deal) for deal in open_deals), 2)
    expected_margin_value = round(sum(_safe_float(deal.deal_value) * _safe_float(deal.margin) for deal in open_deals), 2)
    low_margin_count = sum(1 for deal in open_deals if _safe_float(deal.margin) < 0.2 and _safe_float(deal.deal_value) > 0)

    return {
        "tenant_id": user.tenant_id,
        "booked_revenue": booked_revenue,
        "open_pipeline_value": open_pipeline_value,
        "weighted_revenue_projection": weighted_projection,
        "expected_margin_value": expected_margin_value,
        "low_margin_open_deals": low_margin_count,
        "closed_won_count": len(won),
        "closed_lost_count": len(lost),
    }


@router.get("/analytics/segmentation")
def get_segmentation_analytics(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=["metrics.read"])
    deals = _fetch_tenant_deals(user.tenant_id)

    segments: dict[str, dict[str, float | int]] = defaultdict(lambda: {"count": 0, "deal_value": 0.0, "weighted_value": 0.0})
    for deal in deals:
        segment = deal.segment_tag or "Unassigned"
        segments[segment]["count"] += 1
        segments[segment]["deal_value"] += _safe_float(deal.deal_value)
        segments[segment]["weighted_value"] += _weighted_value(deal)

    rows = [
        {
            "segment": segment,
            "count": int(data["count"]),
            "deal_value": round(float(data["deal_value"]), 2),
            "weighted_value": round(float(data["weighted_value"]), 2),
        }
        for segment, data in segments.items()
    ]
    rows.sort(key=lambda row: (row["deal_value"], row["count"]), reverse=True)

    return {
        "tenant_id": user.tenant_id,
        "segments": rows,
    }


@router.get("/analytics/probability-breakdown")
def get_probability_breakdown(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    user = _authorize(authorization, scopes=["metrics.read"])
    deals = _fetch_tenant_deals(user.tenant_id)

    bucket_counts = {"0-24": 0, "25-49": 0, "50-74": 0, "75-100": 0}
    probabilities: list[float] = []
    confidences: list[int] = []
    factor_totals: dict[str, float] = defaultdict(float)
    factor_counts: dict[str, int] = defaultdict(int)

    for deal in deals:
        probability = _safe_float(deal.probability)
        probabilities.append(probability)
        if deal.probability_confidence is not None:
            confidences.append(int(deal.probability_confidence))

        if probability < 25:
            bucket_counts["0-24"] += 1
        elif probability < 50:
            bucket_counts["25-49"] += 1
        elif probability < 75:
            bucket_counts["50-74"] += 1
        else:
            bucket_counts["75-100"] += 1

        if isinstance(deal.probability_breakdown, dict):
            for key, value in deal.probability_breakdown.items():
                try:
                    factor_totals[key] += float(value)
                    factor_counts[key] += 1
                except (TypeError, ValueError):
                    continue

    factor_averages = {
        key: round((factor_totals[key] / factor_counts[key]), 2)
        for key in sorted(factor_totals.keys())
        if factor_counts[key] > 0
    }
    avg_probability = round(mean(probabilities), 2) if probabilities else 0.0
    avg_confidence = round(mean(confidences), 2) if confidences else 0.0

    deals_payload = [
        {
            "deal_id": deal.id,
            "company": deal.company,
            "stage": deal.stage,
            "probability": _safe_float(deal.probability),
            "probability_confidence": _safe_int(deal.probability_confidence),
            "probability_breakdown": deal.probability_breakdown or {},
            "probability_explanation": deal.probability_explanation,
        }
        for deal in deals
    ]

    return {
        "tenant_id": user.tenant_id,
        "summary": {
            "average_probability": avg_probability,
            "average_confidence": avg_confidence,
            "bucket_counts": bucket_counts,
        },
        "factor_averages": factor_averages,
        "deals": deals_payload,
    }


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
