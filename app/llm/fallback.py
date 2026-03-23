"""Fallback and retry logic for LLM calls."""

from __future__ import annotations

import logging
from typing import Any, Callable

from app.llm.clients import get_client
from app.core.config_llm import get_llm_config

logger = logging.getLogger(__name__)


def safe_generate(
    primary_model: str,
    fallback_model: str,
    prompt: str,
    json_mode: bool = False,
) -> str:
    """Generate with primary model, falling back to secondary on failure.
    
    Args:
        primary_model: Primary model name ('qwen' or 'deepseek')
        fallback_model: Fallback model name
        prompt: Prompt to send to LLM
        json_mode: Whether to request JSON response
        
    Returns:
        LLM response string, or empty string if both fail
    """
    config = get_llm_config()
    
    # Try primary model
    try:
        client = get_client(primary_model)
        response = client.generate(prompt, json_mode=json_mode)
        if response:
            logger.info(
                "llm.fallback.success_primary",
                extra={
                    "event": "llm.fallback.success_primary",
                    "model": primary_model,
                },
            )
            return response
    except Exception as exc:
        logger.warning(
            "llm.fallback.primary_failed",
            extra={
                "event": "llm.fallback.primary_failed",
                "model": primary_model,
                "error": str(exc),
            },
        )
    
    # Fallback to secondary model
    if fallback_model and fallback_model != primary_model:
        try:
            client = get_client(fallback_model)
            response = client.generate(prompt, json_mode=json_mode)
            if response:
                logger.info(
                    "llm.fallback.success_fallback",
                    extra={
                        "event": "llm.fallback.success_fallback",
                        "model": fallback_model,
                    },
                )
                return response
        except Exception as exc:
            logger.warning(
                "llm.fallback.fallback_failed",
                extra={
                    "event": "llm.fallback.fallback_failed",
                    "model": fallback_model,
                    "error": str(exc),
                },
            )
    
    # Last resort: try default model
    try:
        client = get_client(config.DEFAULT_MODEL)
        response = client.generate(prompt, json_mode=json_mode)
        if response:
            logger.info(
                "llm.fallback.success_default",
                extra={
                    "event": "llm.fallback.success_default",
                    "model": config.DEFAULT_MODEL,
                },
            )
            return response
    except Exception as exc:
        logger.error(
            "llm.fallback.all_failed",
            extra={
                "event": "llm.fallback.all_failed",
                "error": str(exc),
            },
        )
    
    return ""


def generate_with_retry(
    model: str,
    prompt: str,
    json_mode: bool = False,
    max_retries: int = 3,
) -> str:
    """Generate with retry logic on the same model.
    
    Args:
        model: Model name ('qwen' or 'deepseek')
        prompt: Prompt to send to LLM
        json_mode: Whether to request JSON response
        max_retries: Maximum number of retry attempts
        
    Returns:
        LLM response string, or empty string if all attempts fail
    """
    last_error: Exception | None = None
    
    for attempt in range(1, max_retries + 1):
        try:
            client = get_client(model)
            response = client.generate(prompt, json_mode=json_mode)
            if response:
                return response
        except Exception as exc:
            last_error = exc
            logger.warning(
                "llm.retry.attempt_failed",
                extra={
                    "event": "llm.retry.attempt_failed",
                    "model": model,
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "error": str(exc),
                },
            )
    
    logger.error(
        "llm.retry.all_failed",
        extra={
            "event": "llm.retry.all_failed",
            "model": model,
            "max_retries": max_retries,
            "error": str(last_error) if last_error else "unknown",
        },
    )
    return ""


def generate_with_model_selection(
    agent_name: str | None = None,
    task_type: str | None = None,
    prompt: str = "",
    json_mode: bool = False,
    use_fallback: bool = True,
) -> str:
    """Generate with intelligent model selection and optional fallback.
    
    Args:
        agent_name: Name of the agent (sdr, sales, negotiation, finance)
        task_type: Type of task (email_generation, sales_reasoning, etc.)
        prompt: Prompt to send to LLM
        json_mode: Whether to request JSON response
        use_fallback: Whether to use fallback model on failure
        
    Returns:
        LLM response string, or empty string if all attempts fail
    """
    from app.llm.router import get_router
    
    router = get_router()
    primary_model = router.get_model_for_request(agent_name=agent_name, task_type=task_type)
    
    # Determine fallback model
    fallback_model = None
    if use_fallback:
        if primary_model == "qwen":
            fallback_model = "deepseek"
        else:
            fallback_model = "qwen"
    
    if use_fallback and fallback_model:
        return safe_generate(primary_model, fallback_model, prompt, json_mode)
    else:
        return generate_with_retry(primary_model, prompt, json_mode)
