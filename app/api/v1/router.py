"""Root API router for v1 endpoints."""

from __future__ import annotations

from app.api._compat import APIRouter
from app.api.v1 import agents, auth, health, prompts, reviews, runs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(agents.router)
api_router.include_router(runs.router)
api_router.include_router(prompts.router)
api_router.include_router(reviews.router)


def get_api_router() -> APIRouter:
    return api_router
