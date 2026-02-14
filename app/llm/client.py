"""LLM client contracts and default adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from time import perf_counter

from app.core.config import get_config
from app.services.llm_client import call_llm


@dataclass(frozen=True)
class LLMRequest:
    prompt_key: str
    prompt: str
    tenant_id: int
    run_id: str
    json_mode: bool = True


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model_name: str
    prompt_hash: str
    latency_ms: int
    generated_at: str


class LLMClient:
    """Default adapter around existing `call_llm` implementation."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        cfg = get_config()
        started = perf_counter()
        text = call_llm(prompt=request.prompt, json_mode=request.json_mode)
        latency_ms = int((perf_counter() - started) * 1000)
        prompt_hash = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()
        return LLMResponse(
            text=text,
            model_name=cfg.OLLAMA_MODEL,
            prompt_hash=prompt_hash,
            latency_ms=latency_ms,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
