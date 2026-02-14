from __future__ import annotations
"""Application entrypoint for both FastAPI and legacy script mode."""

from __future__ import annotations

from pathlib import Path
import sys

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.startup import bootstrap


def create_app() -> FastAPI:
    bootstrap()
    app = FastAPI(title="RIVO API", version="2.0.0")
    app.include_router(api_router)
    return app


app = create_app()
from app.agents.sdr_agent import run_sdr_agent
from app.api.v1.router import get_api_router
from app.core.config import get_config
from app.core.startup import bootstrap


def create_app():
    """Create FastAPI application when dependency is available."""
    try:
        from fastapi import FastAPI
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional deps.
        raise RuntimeError("FastAPI is not installed. Install dependencies from requirements.txt.") from exc

    cfg = get_config()
    app = FastAPI(title=cfg.APP_NAME, version=cfg.APP_VERSION)
    app.include_router(get_api_router())

    @app.get("/")
    def root() -> dict:
        return {"service": cfg.APP_NAME, "version": cfg.APP_VERSION, "api_prefix": cfg.API_PREFIX}

    return app


# Expose ASGI app for `uvicorn app.main:app`.
try:
    app = create_app()
except RuntimeError:
    app = None


if __name__ == "__main__":
    bootstrap()
    # Legacy compatibility path retained during migration window.
    run_sdr_agent()
