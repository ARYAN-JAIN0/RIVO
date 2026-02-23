from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.v1.auth as auth_module
import app.api.v1.endpoints as endpoints_module
from app.core.security import hash_password
from app.database.models import Base, User, Tenant
from app.main import app


def _workspace_tmp_dir() -> Path:
    root = Path(".test_tmp")
    root.mkdir(exist_ok=True)
    path = root / f"auth_api_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _setup_tmp_db():
    tmp_path = _workspace_tmp_dir()
    engine = create_engine(f"sqlite:///{tmp_path/'auth_api.db'}")
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    @contextmanager
    def _session_ctx():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    return Session, _session_ctx


def _seed_admin_user(Session) -> None:
    session = Session()
    try:
        tenant = session.query(Tenant).filter(Tenant.id == 1).first()
        if not tenant:
            session.add(Tenant(id=1, name="default"))
            session.commit()

        user = session.query(User).filter(User.tenant_id == 1, User.email == "admin@example.com").first()
        if not user:
            session.add(
                User(
                    tenant_id=1,
                    email="admin@example.com",
                    hashed_password=hash_password("ChangeThisNow!123"),
                    role="admin",
                    is_active=True,
                )
            )
            session.commit()
    finally:
        session.close()


def test_auth_login_and_protected_route(monkeypatch):
    Session, session_ctx = _setup_tmp_db()
    _seed_admin_user(Session)

    monkeypatch.setattr(auth_module, "get_db_session", session_ctx)
    monkeypatch.setattr(endpoints_module, "get_db_session", session_ctx)

    client = TestClient(app)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "ChangeThisNow!123"},
    )
    assert login_response.status_code == 200
    payload = login_response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]

    leads_response = client.get(
        "/api/v1/leads",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert leads_response.status_code == 200
    assert leads_response.json() == []


def test_auth_login_invalid_credentials(monkeypatch):
    Session, session_ctx = _setup_tmp_db()
    _seed_admin_user(Session)

    monkeypatch.setattr(auth_module, "get_db_session", session_ctx)

    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials."


def test_auth_refresh_works(monkeypatch):
    Session, session_ctx = _setup_tmp_db()
    _seed_admin_user(Session)

    monkeypatch.setattr(auth_module, "get_db_session", session_ctx)

    client = TestClient(app)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "ChangeThisNow!123"},
    )
    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"]
