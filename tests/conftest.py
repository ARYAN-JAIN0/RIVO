from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database.db_handler as db_handler
from app.database.models import Base


@pytest.fixture
def isolated_session_factory(monkeypatch):
    tmp_root = Path(".test_tmp")
    tmp_root.mkdir(exist_ok=True)
    db_path = tmp_root / f"rivo_test_{uuid.uuid4().hex}.db"
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
