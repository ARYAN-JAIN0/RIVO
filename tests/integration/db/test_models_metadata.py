from __future__ import annotations

from app.models import Base
import app.models  # noqa: F401


def test_modular_model_metadata_contains_target_tables():
    expected = {
        "tenants",
        "users",
        "leads",
        "deals",
        "contracts",
        "invoices",
        "pipeline_stages",
        "negotiation_history",
        "email_logs",
        "agent_runs",
        "llm_logs",
    }
    assert expected.issubset(set(Base.metadata.tables.keys()))
