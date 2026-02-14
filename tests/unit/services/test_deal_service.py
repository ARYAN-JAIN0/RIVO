from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.enums import DealStage, LeadStatus
from app.database.models import Base, Lead
from app.services.deal_service import DealService


def _build_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _seed_lead(session):
    lead = Lead(
        name="Deal Lead",
        email="deallead@example.com",
        status=LeadStatus.CONTACTED.value,
        review_status="Approved",
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead


def test_create_and_update_deal_stage():
    session = _build_session()
    lead = _seed_lead(session)
    service = DealService(db=session)

    deal = service.create_deal(lead_id=lead.id, acv=10000, qualification_score=85, company="Acme")
    assert deal.stage == DealStage.QUALIFIED.value

    updated = service.update_stage(deal.id, DealStage.PROPOSAL_SENT.value)
    assert updated is not None
    assert updated.stage == DealStage.PROPOSAL_SENT.value

    session.close()


def test_list_by_stage_returns_matching_deals():
    session = _build_session()
    lead = _seed_lead(session)
    service = DealService(db=session)
    service.create_deal(lead_id=lead.id, acv=5000, qualification_score=70)

    items = service.list_by_stage(DealStage.QUALIFIED.value)
    assert len(items) == 1
    assert items[0].lead_id == lead.id

    session.close()
