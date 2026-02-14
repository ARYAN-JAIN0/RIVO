from __future__ import annotations

import pytest

from app.api._compat import HTTPException
from app.api.v1 import endpoints


def test_health_endpoint_works(monkeypatch):
    monkeypatch.setattr(
        endpoints.RevoOrchestrator,
        "get_system_health",
        lambda self: {"status": "ok"},
    )
    response = endpoints.health()
    assert response == {"status": "ok"}


def test_agent_endpoint_rejects_invalid_agent(monkeypatch):
    class _User:
        tenant_id = 1
        user_id = 1

    monkeypatch.setattr(endpoints, "_authorize", lambda authorization, scopes: _User())

    with pytest.raises(HTTPException) as exc:
        endpoints.run_agent("invalid")
    assert exc.value.status_code == 400


def test_agent_endpoint_requires_auth():
    with pytest.raises(HTTPException) as exc:
        endpoints.run_agent("sdr")
    assert exc.value.status_code == 401
