"""Health endpoints for API v1."""

from __future__ import annotations

from app.api._compat import APIRouter
from app.core.config import get_config

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    cfg = get_config()
    return {"status": "ok", "service": cfg.APP_NAME, "version": cfg.APP_VERSION}
