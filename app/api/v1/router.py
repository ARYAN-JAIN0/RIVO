from __future__ import annotations

"""Root API router for v1 endpoints."""

from fastapi import APIRouter

from app.api.v1 import endpoints

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(endpoints.router)


def get_api_router() -> APIRouter:
    return api_router
