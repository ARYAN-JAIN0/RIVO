from __future__ import annotations

"""Root API router for v1 endpoints."""

from app.api._compat import APIRouter

from app.api.v1 import auth, endpoints

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(endpoints.router)
api_router.include_router(auth.router)


def get_api_router() -> APIRouter:
    return api_router
