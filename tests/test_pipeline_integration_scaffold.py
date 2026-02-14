from __future__ import annotations

import app.orchestrator as orchestrator_module


def test_pipeline_fault_isolation(monkeypatch):
    calls = []

    def ok_agent():
        calls.append("ok")

    def failing_agent():
        calls.append("fail")
        raise RuntimeError("boom")

    monkeypatch.setattr(orchestrator_module, "initialize_vector_store", lambda: None)
    monkeypatch.setattr(orchestrator_module, "initialize_graph_store", lambda: None)

    orch = orchestrator_module.RevoOrchestrator()
    orch.agents = {
        "sdr": ok_agent,
        "sales": failing_agent,
        "negotiation": ok_agent,
    }
    result = orch.run_pipeline(["sdr", "sales", "negotiation"])

    assert calls == ["ok", "fail", "ok"]
    assert result["sdr"] == "success"
    assert result["negotiation"] == "success"
    assert result["sales"].startswith("error:")

