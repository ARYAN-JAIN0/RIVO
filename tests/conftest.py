from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database.db_handler as db_handler
from app.database.models import Base


@pytest.fixture
def isolated_session_factory(monkeypatch, tmp_path):
    db_path = tmp_path / "rivo_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    @contextmanager
    def _get_db_session():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(db_handler, "get_db_session", _get_db_session)
    return TestingSessionLocal

