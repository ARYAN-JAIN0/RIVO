from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_works():
    client = TestClient(app)
    response = client.get('/api/v1/health')
    assert response.status_code == 200


def test_agent_endpoint_rejects_invalid_agent():
    client = TestClient(app)
    response = client.post('/api/v1/agents/invalid/run')
    assert response.status_code == 400
