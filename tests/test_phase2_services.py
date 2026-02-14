from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Lead
from app.services.email_service import EmailService
from app.services.lead_acquisition_service import LeadAcquisitionService
from app.tasks.agent_tasks import execute_agent_task


def _setup_tmp_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'phase2.db'}")
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    @contextmanager
    def get_db_session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    return Session, get_db_session


def test_lead_acquisition_fallback_and_cap(monkeypatch, tmp_path):
    _, get_db_session = _setup_tmp_db(tmp_path)
    import app.services.lead_acquisition_service as mod

    monkeypatch.setattr(mod, "get_db_session", get_db_session)
    svc = LeadAcquisitionService()
    svc.daily_cap = 2
    monkeypatch.setattr(svc, "scrape_public_leads", lambda limit: mod._fallback_leads(limit))

    result = svc.acquire_and_persist(tenant_id=1)
    assert result["created"] <= 2


def test_email_service_sandbox_logs(monkeypatch, tmp_path):
    Session, get_db_session = _setup_tmp_db(tmp_path)
    import app.services.email_service as mod
    from app.database.models import Tenant

    monkeypatch.setattr(mod, "get_db_session", get_db_session)

    s = Session()
    s.add(Tenant(id=1, name="default"))
    s.add(Lead(tenant_id=1, name="A", email="a@test.com", company="Acme"))
    s.commit()
    lead = s.query(Lead).first()
    s.close()

    monkeypatch.setenv("SMTP_SANDBOX_MODE", "true")
    svc = EmailService()
    ok = svc.send_email(tenant_id=1, lead_id=lead.id, to_email=lead.email, subject="Hello", html_body="<p>h</p>", text_body="h")
    assert ok is True


def test_execute_agent_task_unknown(monkeypatch, tmp_path):
    _, get_db_session = _setup_tmp_db(tmp_path)
    import app.tasks.agent_tasks as mod

    monkeypatch.setattr(mod, "get_db_session", get_db_session)
    result = execute_agent_task.run(agent_name="unknown", tenant_id=1)
    assert result["status"] == "failed"
