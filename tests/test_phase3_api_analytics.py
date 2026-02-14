from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.jwt import create_token_pair
from app.core.config import get_config
from app.database.models import Base, Deal, Lead, Tenant
from app.main import app


def _workspace_tmp_dir() -> Path:
    root = Path(".test_tmp")
    root.mkdir(exist_ok=True)
    path = root / f"phase3_api_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _setup_tmp_db():
    tmp_path = _workspace_tmp_dir()
    engine = create_engine(f"sqlite:///{tmp_path/'phase3_api.db'}")
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    @contextmanager
    def _session_ctx():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    return Session, _session_ctx


def _auth_header(role: str = "admin", tenant_id: int = 1, user_id: int = 1) -> dict[str, str]:
    cfg = get_config()
    token = create_token_pair(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        secret=cfg.JWT_SECRET,
        permissions_version=cfg.JWT_PERMISSIONS_VERSION,
    ).access_token
    return {"Authorization": f"Bearer {token}"}


def _seed_deal(Session) -> int:
    session = Session()
    try:
        tenant = session.query(Tenant).filter(Tenant.id == 1).first()
        if not tenant:
            session.add(Tenant(id=1, name="default"))
            session.commit()

        email = f"phase3_{uuid.uuid4().hex[:12]}@example.com"
        lead = Lead(
            tenant_id=1,
            name="Phase3 Lead",
            email=email,
            company="Acme",
            industry="SaaS",
            status="Contacted",
        )
        session.add(lead)
        session.commit()
        session.refresh(lead)

        deal = Deal(
            tenant_id=1,
            lead_id=lead.id,
            company="Acme",
            stage="Lead",
            status="Open",
            deal_value=50000,
            probability=50.0,
            probability_confidence=55,
            segment_tag="SMB",
        )
        session.add(deal)
        session.commit()
        session.refresh(deal)
        return deal.id
    finally:
        session.close()


def test_phase3_analytics_and_deal_routes(monkeypatch):
    import app.api.v1.endpoints as endpoints_mod
    import app.services.opportunity_scoring_service as score_mod
    import app.services.rag_service as rag_mod
    import app.services.sales_intelligence_service as sis_mod

    Session, session_ctx = _setup_tmp_db()
    monkeypatch.setattr(endpoints_mod, "get_db_session", session_ctx)
    monkeypatch.setattr(rag_mod, "get_db_session", session_ctx)
    monkeypatch.setattr(sis_mod, "get_db_session", session_ctx)

    monkeypatch.setattr(
        score_mod.OpportunityScoringService,
        "_llm_score",
        staticmethod(lambda lead, transcript='': (65, "test-score")),
    )

    client = TestClient(app)
    headers = _auth_header(role="admin")
    deal_id = _seed_deal(Session)

    pipeline = client.get("/api/v1/analytics/pipeline", headers=headers)
    assert pipeline.status_code == 200
    assert pipeline.json()["pipeline_value"] >= 50000

    forecast = client.get("/api/v1/analytics/forecast", headers=headers)
    assert forecast.status_code == 200
    assert "monthly" in forecast.json()

    revenue = client.get("/api/v1/analytics/revenue", headers=headers)
    assert revenue.status_code == 200
    assert revenue.json()["open_pipeline_value"] >= 50000

    segmentation = client.get("/api/v1/analytics/segmentation", headers=headers)
    assert segmentation.status_code == 200
    assert any(row["segment"] == "SMB" for row in segmentation.json()["segments"])

    probability = client.get("/api/v1/analytics/probability-breakdown", headers=headers)
    assert probability.status_code == 200
    assert probability.json()["summary"]["average_probability"] > 0

    rescore = client.post(f"/api/v1/sales/deals/{deal_id}/rescore", headers=headers)
    assert rescore.status_code == 200
    assert rescore.json()["probability"] is not None

    override = client.post(
        f"/api/v1/sales/deals/{deal_id}/manual-override",
        headers=headers,
        json={"stage": "Qualified", "probability": 72.5, "reason": "sales review"},
    )
    assert override.status_code == 200
    assert override.json()["stage"] == "Qualified"
    assert override.json()["probability"] == 72.5
