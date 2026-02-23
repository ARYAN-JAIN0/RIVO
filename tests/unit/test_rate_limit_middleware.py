from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

from app.api._compat import FastAPI
rate_limit_module = importlib.import_module("app.middleware.rate_limit")


def test_rate_limit_middleware_no_slowapi_does_not_crash(monkeypatch):
    monkeypatch.setattr(rate_limit_module, "SLOWAPI_AVAILABLE", False)

    app = FastAPI()
    app.add_middleware(rate_limit_module.RateLimitMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
