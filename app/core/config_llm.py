"""Multi-model LLM configuration for RIVO.

This module provides configuration for routing tasks to different LLM models
(Qwen for generation, DeepSeek for reasoning).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class LLMModelConfig:
    """Configuration for a single LLM model."""
    model_name: str
    base_url: str


@dataclass(frozen=True)
class LLMConfig:
    """Multi-model LLM configuration."""
    MULTI_MODEL: bool
    MODEL_CONFIG: dict[str, LLMModelConfig]
    DEFAULT_MODEL: str
    REASONING_MODELS: list[str]
    GENERATION_MODELS: list[str]


def _build_llm_config() -> LLMConfig:
    """Build LLM config from environment variables."""
    multi_model = os.getenv("MULTI_MODEL", "true").lower() in ("true", "1", "yes")

    # Model configurations
    # Hardware note: 4GB VRAM supports up to 8B models (7b-8b recommended)
    # Using qwen2.5:7b for generation, deepseek-r1:8b for reasoning
    qwen_name = os.getenv("QWEN_MODEL", "qwen2.5:7b")
    deepseek_name = os.getenv("DEEPSEEK_MODEL", "deepseek-r1:8b")
    ollama_base = os.getenv("OLLAMA_URL", "http://localhost:11434")

    model_config = {
        "qwen": LLMModelConfig(
            model_name=qwen_name,
            base_url=ollama_base,
        ),
        "deepseek": LLMModelConfig(
            model_name=deepseek_name,
            base_url=ollama_base,
        ),
    }

    return LLMConfig(
        MULTI_MODEL=multi_model,
        MODEL_CONFIG=model_config,
        DEFAULT_MODEL="qwen",
        REASONING_MODELS=["deepseek"],
        GENERATION_MODELS=["qwen"],
    )


@lru_cache(maxsize=2)
def get_llm_config() -> LLMConfig:
    """Get the multi-model LLM configuration."""
    return _build_llm_config()


# Agent to model mapping
AGENT_MODEL_MAP = {
    "sdr": "qwen",
    "sales": "deepseek",
    "negotiation": "deepseek",
    "finance": "qwen",
}


# Task type to model mapping
TASK_TYPE_MAP = {
    "email_generation": "qwen",
    "sales_reasoning": "deepseek",
    "negotiation": "deepseek",
    "finance": "qwen",
    "strategy": "deepseek",
    "default": "qwen",
}
