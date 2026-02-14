"""Review decision endpoints for API v1."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.api._compat import APIRouter, Header, HTTPException, status
from app.api.v1._authz import authorize, map_auth_error
from app.services.review_service import ReviewService

router = APIRouter(tags=["reviews"])
review_service = ReviewService()


class ReviewDecisionRequest(BaseModel):
    decision: str = Field(min_length=2, max_length=40)
    edited_email: str | None = Field(default=None, max_length=10000)
    notes: str | None = Field(default=None, max_length=2000)


@router.post("/reviews/{entity_type}/{entity_id}/decision", status_code=status.HTTP_201_CREATED)
def review_decision(
    entity_type: str,
    entity_id: int,
    payload: ReviewDecisionRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    try:
        user = authorize(authorization=authorization, scopes=["reviews.decision"])
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc

    if entity_type.lower() != "lead":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Phase 1 endpoint supports entity_type='lead' only.",
        )

    review_service.mark_decision(
        lead_id=entity_id,
        decision=payload.decision,
        edited_email=payload.edited_email,
        actor=str(user.user_id),
    )
    return {"audit_id": f"review-{entity_type}-{entity_id}", "status": "recorded"}
