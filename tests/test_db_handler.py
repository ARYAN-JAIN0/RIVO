from __future__ import annotations

from datetime import datetime

import app.database.db_handler as db_handler
from app.core.enums import LeadStatus, ReviewStatus
from app.database.models import Contract, Deal, Lead, Invoice


def test_save_draft_does_not_change_status(isolated_session_factory):
    session = isolated_session_factory()
    lead = Lead(name="Test", email="test@example.com", status=LeadStatus.NEW.value, review_status=ReviewStatus.NEW.value)
    session.add(lead)
    session.commit()
    session.refresh(lead)
    lead_id = lead.id
    session.close()

    db_handler.save_draft(lead_id, "Draft body", 88, ReviewStatus.PENDING.value)

    verify = isolated_session_factory()
    updated = verify.query(Lead).filter(Lead.id == lead_id).first()
    assert updated is not None
    assert updated.status == LeadStatus.NEW.value
    assert updated.review_status == ReviewStatus.PENDING.value
    verify.close()


def test_mark_review_decision_approved_updates_status(isolated_session_factory):
    session = isolated_session_factory()
    lead = Lead(name="Test 2", email="test2@example.com", status=LeadStatus.NEW.value, review_status=ReviewStatus.PENDING.value)
    session.add(lead)
    session.commit()
    session.refresh(lead)
    lead_id = lead.id
    session.close()

    db_handler.mark_review_decision(lead_id, ReviewStatus.APPROVED.value, edited_email="Approved draft")

    verify = isolated_session_factory()
    updated = verify.query(Lead).filter(Lead.id == lead_id).first()
    assert updated is not None
    assert updated.status == LeadStatus.CONTACTED.value
    assert updated.review_status == ReviewStatus.APPROVED.value
    assert updated.last_contacted is not None
    verify.close()


def test_create_invoice_deduplication(isolated_session_factory):
    session = isolated_session_factory()
    lead = Lead(name="Invoice Lead", email="invoice@example.com", status=LeadStatus.CONTACTED.value)
    session.add(lead)
    session.commit()
    session.refresh(lead)

    deal = Deal(
        lead_id=lead.id,
        company="TestCo",
        acv=10000,
        qualification_score=90,
        stage="Proposal Sent",
        review_status=ReviewStatus.APPROVED.value,
        created_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    session.add(deal)
    session.commit()
    session.refresh(deal)

    contract = Contract(
        deal_id=deal.id,
        lead_id=lead.id,
        status="Signed",
        contract_terms="Standard terms",
        contract_value=10000,
        review_status=ReviewStatus.APPROVED.value,
        last_updated=datetime.utcnow(),
    )
    session.add(contract)
    session.commit()
    session.refresh(contract)
    contract_id = contract.id
    lead_id = lead.id
    session.close()

    invoice_id_1 = db_handler.create_invoice(contract_id=contract_id, lead_id=lead_id, amount=10000, due_date="2026-03-01")
    invoice_id_2 = db_handler.create_invoice(contract_id=contract_id, lead_id=lead_id, amount=10000, due_date="2026-03-01")

    verify = isolated_session_factory()
    invoices = verify.query(Invoice).filter(Invoice.contract_id == contract_id).all()
    assert invoice_id_1 == invoice_id_2
    assert len(invoices) == 1
    verify.close()

