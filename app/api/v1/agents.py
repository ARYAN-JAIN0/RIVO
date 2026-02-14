"""Agent execution endpoints for API v1."""

from __future__ import annotations

from app.api._compat import APIRouter, Header, HTTPException, status
from app.api.v1._authz import authorize, map_auth_error
from app.schemas.runs import RunResponse, RunTriggerRequest
from app.tasks.agent_tasks import execute_registered_task

router = APIRouter(tags=["agents"])

SUPPORTED_AGENTS = {"sdr", "sales", "negotiation", "finance"}


@router.post("/agents/{agent_name}/run", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def run_agent(
    agent_name: str,
    payload: RunTriggerRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> RunResponse:
    try:
        user = authorize(authorization=authorization, scopes=[f"agents.{agent_name}.run"])
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc

    if agent_name not in SUPPORTED_AGENTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown agent: {agent_name}")

    result = execute_registered_task(
        task_key=f"agents.{agent_name}",
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        payload=payload.payload,
    )
    return RunResponse(**result)


@router.post("/pipeline/run", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def run_pipeline(
    payload: RunTriggerRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> RunResponse:
    try:
        user = authorize(authorization=authorization, scopes=["agents.pipeline.run"])
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc

    result = execute_registered_task(
        task_key="agents.pipeline",
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        payload=payload.payload,
    )
    return RunResponse(**result)
