from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.enums import ContractStatus, DealStage, LeadStatus
from app.database.models import Base, Deal, Lead
from app.services.contract_service import ContractService


def _build_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _seed_lead_and_deal(session):
    lead = Lead(
        name="Contract Lead",
        email="contractlead@example.com",
        status=LeadStatus.CONTACTED.value,
        review_status="Approved",
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)

    deal = Deal(
        lead_id=lead.id,
        company="Acme",
        acv=20000,
        qualification_score=88,
        stage=DealStage.PROPOSAL_SENT.value,
        review_status="Approved",
    )
    session.add(deal)
    session.commit()
    session.refresh(deal)
    return lead, deal


def test_create_contract_and_mark_signed():
    session = _build_session()
    lead, deal = _seed_lead_and_deal(session)
    service = ContractService(db=session)

    contract = service.create_contract(
        deal_id=deal.id,
        lead_id=lead.id,
        contract_terms="Net 30 terms",
        contract_value=20000,
    )
    assert contract.status == ContractStatus.NEGOTIATING.value

    updated = service.update_status(contract.id, ContractStatus.SIGNED.value)
    assert updated is not None
    assert updated.status == ContractStatus.SIGNED.value
    assert updated.signed_date is not None

    session.close()


def test_update_negotiation_fields():
    session = _build_session()
    lead, deal = _seed_lead_and_deal(session)
    service = ContractService(db=session)
    contract = service.create_contract(
        deal_id=deal.id,
        lead_id=lead.id,
        contract_terms="Initial terms",
        contract_value=10000,
    )

    updated = service.update_negotiation(
        contract.id,
        objections="Price concern",
        proposed_solutions="Quarterly billing",
        confidence_score=82,
    )
    assert updated is not None
    assert updated.objections == "Price concern"
    assert updated.proposed_solutions == "Quarterly billing"
    assert updated.negotiation_points == "confidence=82"

    session.close()
