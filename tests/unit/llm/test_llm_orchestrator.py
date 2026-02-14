from __future__ import annotations

from app.llm.client import LLMResponse
from app.llm.orchestrator import LLMOrchestrator


class DummyClient:
    def generate(self, request):
        return LLMResponse(
            text='{"ok": true}',
            model_name="dummy",
            prompt_hash="hash",
            latency_ms=3,
            generated_at="2026-02-14T00:00:00Z",
        )


def test_llm_orchestrator_generate_ok():
    orchestrator = LLMOrchestrator(
        client=DummyClient(),
        prompt_registry={"prompt.key": lambda ctx: "hello world"},
    )
    result = orchestrator.generate("prompt.key", {"x": 1}, tenant_id=1, run_id="run-1")
    assert result.validation_status == "ok"
    assert result.model_name == "dummy"
    assert result.confidence_score > 0


def test_llm_orchestrator_pre_validation_failure():
    orchestrator = LLMOrchestrator(
        client=DummyClient(),
        prompt_registry={"prompt.empty": lambda ctx: " "},
    )
    result = orchestrator.generate("prompt.empty", {}, tenant_id=1, run_id="run-2")
    assert result.validation_status == "failed_pre_validation"
    assert result.failure_reason is not None
