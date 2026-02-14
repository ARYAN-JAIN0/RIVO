from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Deal, Lead, Tenant
from app.services.opportunity_scoring_service import OpportunityScoringService
from app.services.rag_service import RAGService
from app.services.sales_intelligence_service import SalesIntelligenceService


def _setup_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'phase3.db'}")
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


def test_probability_scoring_formula(monkeypatch):
    class DummyLead:
        role = "CTO"
        verified_insight = "Budget approved and urgent migration this quarter"
        followup_count = 0

    svc = OpportunityScoringService()
    monkeypatch.setattr(svc, "_llm_score", lambda lead, transcript='': (80, "intent strong"))
    score = svc.score(DummyLead(), email_log_count=3)
    assert score.final_probability == round((0.6 * score.rule_score) + (0.4 * 80), 2)


def test_margin_calculation():
    result = SalesIntelligenceService.calculate_margin(100000, 70000)
    assert result.margin == 0.3
    assert result.low_margin_flag is False


def test_rag_retrieval(monkeypatch, tmp_path):
    Session, session_ctx = _setup_db(tmp_path)
    import app.services.rag_service as rag_mod
    monkeypatch.setattr(rag_mod, "get_db_session", session_ctx)

    s = Session()
    s.add(Tenant(id=1, name="default"))
    s.commit()
    s.close()

    rag = RAGService()
    rag.ingest_knowledge(tenant_id=1, entity_type="deal", entity_id=1, title="Won SaaS deal", content="SaaS buyer wanted urgent rollout", source="test")
    rag.ingest_knowledge(tenant_id=1, entity_type="deal", entity_id=2, title="Lost retail deal", content="Retail buyer had no budget", source="test")

    rows = rag.retrieve(tenant_id=1, query="urgent saas rollout", top_k=1)
    assert len(rows) == 1
    assert rows[0].title in {"Won SaaS deal", "Lost retail deal"}


def test_sales_create_update_and_forecast_fields(monkeypatch, tmp_path):
    Session, session_ctx = _setup_db(tmp_path)
    import app.services.sales_intelligence_service as sis_mod

    monkeypatch.setattr(sis_mod, "get_db_session", session_ctx)
    monkeypatch.setattr(sis_mod.RAGService, "ingest_knowledge", lambda *args, **kwargs: 1)

    s = Session()
    s.add(Tenant(id=1, name="default"))
    lead = Lead(tenant_id=1, name="Alex", email="alex@acme.com", company="Acme", company_size="enterprise", industry="saas", status="Contacted")
    s.add(lead)
    s.commit()
    s.refresh(lead)
    s.close()

    svc = SalesIntelligenceService()
    deal = svc.create_or_update_deal(lead)
    assert deal.deal_value is not None
    assert deal.probability is not None
    assert deal.segment_tag is not None

    s = Session()
    fetched = s.query(Deal).filter(Deal.id == deal.id).first()
    assert fetched is not None
    assert fetched.forecast_month is not None
    s.close()
