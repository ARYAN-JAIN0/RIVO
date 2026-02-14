"""Run management and observability endpoints for API v1."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone

from app.api._compat import APIRouter, Header, HTTPException, Query, status
from app.api.v1._authz import authorize, map_auth_error
from app.schemas.runs import ManualOverrideRequest, RunListItem, RunResponse, RunRetryRequest
from app.tasks.agent_tasks import dead_letter_queue, execute_registered_task, run_service

router = APIRouter(tags=["runs"])

manual_override_log: dict[str, dict] = {}


@router.get("/runs")
def list_runs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    try:
        authorize(authorization=authorization, scopes=["runs.read"])
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc

    records = run_service.list_runs()
    page = records[offset : offset + limit]
    return {
        "items": [RunListItem(**record.__dict__).model_dump() for record in page],
        "total": len(records),
        "limit": limit,
        "offset": offset,
    }


@router.get("/runs/{run_id}")
def get_run(run_id: str, authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    try:
        authorize(authorization=authorization, scopes=["runs.read"])
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc

    record = run_service.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")
    return RunListItem(**record.__dict__).model_dump()


@router.post("/runs/{run_id}/retry", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def retry_run(
    run_id: str,
    payload: RunRetryRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> RunResponse:
    try:
        user = authorize(authorization=authorization, scopes=["runs.retry"])
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc

    original = run_service.get_run(run_id)
    if original is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")

    result = execute_registered_task(
        task_key=original.agent_name,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        payload={"retry_of": run_id},
    )
    return RunResponse(**result)


@router.post("/runs/{run_id}/manual-override")
def manual_override(
    run_id: str,
    payload: ManualOverrideRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    try:
        user = authorize(authorization=authorization, scopes=["runs.override"])
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc

    record = run_service.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")

    run_service.update_status(run_id=run_id, status=f"manual_override:{payload.action}")
    manual_override_log[run_id] = {
        "action": payload.action,
        "reason": payload.reason,
        "actor": payload.actor or str(user.user_id),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"run_id": run_id, "audit_id": f"override-{run_id}", "status": "overridden"}


@router.get("/logs/agents")
def agent_logs(
    limit: int = Query(default=50, ge=1, le=500),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    try:
        authorize(authorization=authorization, scopes=["logs.read"])
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc

    return {"items": dead_letter_queue[-limit:]}


@router.get("/metrics/agents")
def agent_metrics(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    try:
        authorize(authorization=authorization, scopes=["metrics.read"])
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc

    by_agent: dict[str, Counter] = defaultdict(Counter)
    for record in run_service.list_runs():
        by_agent[record.agent_name][record.status] += 1

    return {"metrics": {agent: dict(counter) for agent, counter in by_agent.items()}}
