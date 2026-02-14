from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.startup import bootstrap


def create_app() -> FastAPI:
    bootstrap()
    app = FastAPI(title="RIVO API", version="2.0.0")
    app.include_router(api_router)
    return app


app = create_app()
