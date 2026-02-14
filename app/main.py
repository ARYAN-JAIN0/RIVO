from __future__ import annotations

"""Application entrypoint for FastAPI and legacy CLI execution."""

from app.agents.sdr_agent import run_sdr_agent
from app.api._compat import FastAPI
from app.api.v1.router import api_router
from app.core.config import get_config
from app.core.startup import bootstrap


def create_app() -> FastAPI:
    """Create configured ASGI application."""
    bootstrap()
    cfg = get_config()
    app = FastAPI(title=cfg.APP_NAME, version=cfg.APP_VERSION)
    app.include_router(api_router)

    @app.get("/")
    def root() -> dict:
        return {"service": cfg.APP_NAME, "version": cfg.APP_VERSION, "api_prefix": cfg.API_PREFIX}

    return app


app = create_app()


if __name__ == "__main__":
    # Legacy compatibility path retained during migration window.
    run_sdr_agent()
