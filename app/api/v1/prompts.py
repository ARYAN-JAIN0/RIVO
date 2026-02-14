"""Prompt management endpoints for API v1."""

from __future__ import annotations

from app.api._compat import APIRouter, Header, HTTPException, status
from app.api.v1._authz import authorize, map_auth_error
from app.llm.prompt_templates.defaults import DEFAULT_PROMPT_REGISTRY
from app.schemas.prompts import PromptUpdateRequest, PromptUpdateResponse

router = APIRouter(tags=["prompts"])

# Phase-1 in-memory prompt template storage.
prompt_store: dict[str, str] = {
    key: renderer({"lead_name": "example", "company": "example", "invoice_code": "INV", "amount": 0})
    for key, renderer in DEFAULT_PROMPT_REGISTRY.items()
}


@router.patch("/prompts/{prompt_key}", response_model=PromptUpdateResponse)
def update_prompt(
    prompt_key: str,
    payload: PromptUpdateRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> PromptUpdateResponse:
    try:
        authorize(authorization=authorization, scopes=["prompts.update"])
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc

    if prompt_key not in prompt_store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown prompt key: {prompt_key}")

    prompt_store[prompt_key] = payload.template
    return PromptUpdateResponse(prompt_key=prompt_key, updated_by=payload.updated_by, updated=True)
