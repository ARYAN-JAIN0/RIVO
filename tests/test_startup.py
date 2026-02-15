from __future__ import annotations

import pytest

import app.core.startup as startup_module


class _Cfg:
    def __init__(self, required: bool) -> None:
        self.DB_CONNECTIVITY_REQUIRED = required
        self.ENV = "development"
        self.DATABASE_URL = "postgresql+psycopg2://bad:bad@localhost:5432/rivo"

    @property
    def is_production(self) -> bool:
        return False


def test_startup_skips_raise_when_db_optional_and_unreachable(monkeypatch):
    monkeypatch.setattr(startup_module, "get_config", lambda: _Cfg(required=False))
    monkeypatch.setattr(startup_module, "verify_database_connection", lambda: False)

    startup_module.validate_startup_config()


def test_startup_raises_when_db_required_and_unreachable(monkeypatch):
    monkeypatch.setattr(startup_module, "get_config", lambda: _Cfg(required=True))
    monkeypatch.setattr(startup_module, "verify_database_connection", lambda: False)

    with pytest.raises(RuntimeError, match="Database connectivity check failed"):
        startup_module.validate_startup_config()
