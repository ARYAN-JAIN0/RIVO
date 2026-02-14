"""LLM orchestrator contract with deterministic guard rails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.llm.client import LLMClient, LLMRequest, LLMResponse
from app.llm.prompt_templates.defaults import DEFAULT_PROMPT_REGISTRY
from app.llm.scoring.heuristics import estimate_confidence
from app.llm.validators.basic import validate_non_empty_output

PromptRenderer = Callable[[dict], str]
Validator = Callable[[str], tuple[bool, str | None]]


@dataclass(frozen=True)
class LLMResult:
    text: str
    model_name: str
    prompt_hash: str
    latency_ms: int
    confidence_score: int
    validation_status: str
    failure_reason: str | None


class LLMOrchestrator:
    """Unified generation entrypoint for API/worker callers."""

    def __init__(
        self,
        client: LLMClient | None = None,
        prompt_registry: dict[str, PromptRenderer] | None = None,
        pre_validators: list[Validator] | None = None,
        post_validators: list[Validator] | None = None,
    ) -> None:
        self.client = client or LLMClient()
        self.prompt_registry = prompt_registry or dict(DEFAULT_PROMPT_REGISTRY)
        self.pre_validators = pre_validators or [validate_non_empty_output]
        self.post_validators = post_validators or [validate_non_empty_output]

    def generate(self, prompt_key: str, context: dict, tenant_id: int, run_id: str) -> LLMResult:
        """Generate LLM output with deterministic validation before and after call."""
        renderer = self.prompt_registry.get(prompt_key)
        if renderer is None:
            raise KeyError(f"Unknown prompt key: {prompt_key}")

        prompt = renderer(context)
        for validator in self.pre_validators:
            ok, reason = validator(prompt)
            if not ok:
                return LLMResult(
                    text="",
                    model_name="n/a",
                    prompt_hash="n/a",
                    latency_ms=0,
                    confidence_score=0,
                    validation_status="failed_pre_validation",
                    failure_reason=reason,
                )

        response: LLMResponse = self.client.generate(
            LLMRequest(
                prompt_key=prompt_key,
                prompt=prompt,
                tenant_id=tenant_id,
                run_id=run_id,
                json_mode=True,
            )
        )

        for validator in self.post_validators:
            ok, reason = validator(response.text)
            if not ok:
                return LLMResult(
                    text=response.text,
                    model_name=response.model_name,
                    prompt_hash=response.prompt_hash,
                    latency_ms=response.latency_ms,
                    confidence_score=0,
                    validation_status="failed_post_validation",
                    failure_reason=reason,
                )

        confidence = estimate_confidence(response.text)
        return LLMResult(
            text=response.text,
            model_name=response.model_name,
            prompt_hash=response.prompt_hash,
            latency_ms=response.latency_ms,
            confidence_score=confidence,
            validation_status="ok",
            failure_reason=None,
        )
