from __future__ import annotations

import app.orchestrator as orchestrator_module


def test_health_uses_pending_review_source(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "fetch_leads_by_status", lambda status: [1, 2] if status == "New" else [3])
    monkeypatch.setattr(orchestrator_module, "fetch_pending_reviews", lambda: [1, 2, 3, 4])
    monkeypatch.setattr(orchestrator_module, "fetch_deals_by_status", lambda stage: [1] if stage == "Qualified" else [])
    monkeypatch.setattr(orchestrator_module, "fetch_contracts_by_status", lambda status: [])
    monkeypatch.setattr(orchestrator_module, "fetch_invoices_by_status", lambda status: [])
    monkeypatch.setattr(orchestrator_module, "initialize_vector_store", lambda: None)
    monkeypatch.setattr(orchestrator_module, "initialize_graph_store", lambda: None)

    orch = orchestrator_module.RevoOrchestrator()
    health = orch.get_system_health()
    assert health["sdr"]["pending_review"] == 4

