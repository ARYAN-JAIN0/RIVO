from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.enums import ContractStatus, DealStage, InvoiceStatus, LeadStatus
from app.database.models import Base, Contract, Deal, Lead
from app.services.invoice_service import InvoiceService


def _build_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _seed_lead_deal_contract(session):
    lead = Lead(
        name="Invoice Lead",
        email="invoicelead@example.com",
        status=LeadStatus.CONTACTED.value,
        review_status="Approved",
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)

    deal = Deal(
        lead_id=lead.id,
        company="Acme",
        acv=15000,
        qualification_score=80,
        stage=DealStage.PROPOSAL_SENT.value,
        review_status="Approved",
    )
    session.add(deal)
    session.commit()
    session.refresh(deal)

    contract = Contract(
        deal_id=deal.id,
        lead_id=lead.id,
        status=ContractStatus.SIGNED.value,
        contract_terms="Net 30",
        contract_value=15000,
        review_status="Approved",
    )
    session.add(contract)
    session.commit()
    session.refresh(contract)
    return lead, deal, contract


def test_create_invoice_and_update_status():
    session = _build_session()
    lead, _deal, contract = _seed_lead_deal_contract(session)
    service = InvoiceService(db=session)

    invoice = service.create_invoice(
        contract_id=contract.id,
        lead_id=lead.id,
        amount=15000,
        due_date=date(2026, 3, 1),
    )
    assert invoice.status == InvoiceStatus.SENT.value

    overdue = service.update_status(invoice.id, InvoiceStatus.OVERDUE.value, days_overdue=8, dunning_stage=1)
    assert overdue is not None
    assert overdue.status == InvoiceStatus.OVERDUE.value
    assert overdue.days_overdue == 8
    assert overdue.dunning_stage == 1

    session.close()


def test_mark_paid_and_update_draft():
    session = _build_session()
    lead, _deal, contract = _seed_lead_deal_contract(session)
    service = InvoiceService(db=session)
    invoice = service.create_invoice(
        contract_id=contract.id,
        lead_id=lead.id,
        amount=10000,
        due_date="2026-03-05",
    )

    updated = service.update_draft(invoice.id, "Payment reminder body", 77)
    assert updated is not None
    assert updated.draft_message == "Payment reminder body"
    assert updated.confidence_score == 77

    success = service.mark_paid(invoice.id)
    assert success is True
    paid = service.get_invoice(invoice.id)
    assert paid is not None
    assert paid.status == InvoiceStatus.PAID.value
    assert paid.payment_date is not None

    session.close()
