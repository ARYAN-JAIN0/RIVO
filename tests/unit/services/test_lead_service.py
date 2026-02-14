from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.enums import LeadStatus
from app.database.models import Base
from app.services.lead_service import LeadService


def _build_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def test_create_and_fetch_lead():
    session = _build_session()
    service = LeadService(db=session)

    created = service.create_lead(
        {
            "name": "Ari",
            "email": "ari@example.com",
            "status": LeadStatus.NEW.value,
            "review_status": "New",
        }
    )
    fetched = service.get_lead(created.id)
    assert fetched is not None
    assert fetched.email == "ari@example.com"

    session.close()


def test_update_status_sets_last_contacted_for_contacted():
    session = _build_session()
    service = LeadService(db=session)
    lead = service.create_lead(
        {
            "name": "Taylor",
            "email": "taylor@example.com",
            "status": LeadStatus.NEW.value,
            "review_status": "New",
        }
    )

    updated = service.update_status(lead.id, LeadStatus.CONTACTED.value)
    assert updated is not None
    assert updated.status == LeadStatus.CONTACTED.value
    assert updated.last_contacted is not None

    session.close()
