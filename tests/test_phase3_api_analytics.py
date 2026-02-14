from __future__ import annotations

from fastapi.testclient import TestClient

from app.database.db import engine
from app.database.models import Base
from app.main import app


Base.metadata.create_all(bind=engine)
client = TestClient(app)


def test_analytics_endpoints_exist():
    assert client.get('/api/v1/analytics/pipeline').status_code == 200
    assert client.get('/api/v1/analytics/forecast').status_code == 200
    assert client.get('/api/v1/analytics/revenue').status_code == 200
    assert client.get('/api/v1/analytics/segmentation').status_code == 200
    assert client.get('/api/v1/analytics/probability-breakdown').status_code == 200
