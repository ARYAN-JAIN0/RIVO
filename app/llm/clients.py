"""Multi-model LLM clients for RIVO.

Provides separate clients for Qwen (generation) and DeepSeek (reasoning).
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import requests

from app.core.config_llm import get_llm_config, LLMModelConfig

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, model_config: LLMModelConfig):
        self.model = model_config.model_name
        self.url = f"{model_config.base_url}/api/generate"

    @abstractmethod
    def generate(self, prompt: str, json_mode: bool = False) -> str:
        """Generate a response from the LLM."""
        pass

    def _call_api(self, prompt: str, json_mode: bool = False, max_retries: int = 3) -> str:
        """Make API call with retry logic."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"

        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    self.url,
                    json=payload,
                    timeout=(5, 90),
                )
                response.raise_for_status()
                body = response.json()
                return body.get("response", "")
            except (requests.exceptions.RequestException, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "llm.client.call_failed",
                    extra={
                        "event": "llm.client.call_failed",
                        "model": self.model,
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )
                if attempt < max_retries:
                    time.sleep(min(2 * attempt, 5))
                else:
                    break

        logger.error(
            "llm.client.unavailable",
            extra={
                "event": "llm.client.unavailable",
                "model": self.model,
                "error": str(last_error) if last_error else "unknown",
            },
        )
        return ""


class QwenClient(BaseLLMClient):
    """Qwen client for generation tasks (emails, finance, etc.)."""

    def __init__(self):
        config = get_llm_config()
        super().__init__(config.MODEL_CONFIG["qwen"])
        logger.info("llm.client.initialized", extra={"event": "llm.client.initialized", "model": self.model})

    def generate(self, prompt: str, json_mode: bool = False) -> str:
        """Generate content using Qwen."""
        return self._call_api(prompt, json_mode=json_mode)


class DeepSeekClient(BaseLLMClient):
    """DeepSeek client for reasoning tasks (strategy, negotiation analysis)."""

    def __init__(self):
        config = get_llm_config()
        super().__init__(config.MODEL_CONFIG["deepseek"])
        logger.info("llm.client.initialized", extra={"event": "llm.client.initialized", "model": self.model})

    def generate(self, prompt: str, json_mode: bool = False) -> str:
        """Generate reasoning using DeepSeek."""
        return self._call_api(prompt, json_mode=json_mode)


# Client registry for easy access
_clients: dict[str, BaseLLMClient] = {}


def get_client(model_name: str) -> BaseLLMClient:
    """Get or create a client for the specified model."""
    if model_name not in _clients:
        if model_name == "qwen":
            _clients[model_name] = QwenClient()
        elif model_name == "deepseek":
            _clients[model_name] = DeepSeekClient()
        else:
            raise ValueError(f"Unknown model: {model_name}")
    return _clients[model_name]
