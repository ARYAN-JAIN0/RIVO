"""Unified LLM facade that combines all multi-model components.

This module provides a high-level interface for LLM operations that integrates:
- Multi-model routing (Qwen for generation, DeepSeek for reasoning)
- Validation with Pydantic schemas
- Caching
- Fallback/retry logic
- Feature engineering

Usage:
    from app.llm.facade import generate_email, generate_strategy
    
    # Email generation (uses Qwen)
    email = generate_email(lead_data, schema=EmailOutput)
    
    # Strategy reasoning (uses DeepSeek)
    strategy = generate_strategy(deal_data, schema=StrategyOutput)
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.cache import cached_llm_call, get_cache_key
from app.core.feature_engineering import extract_features, features_to_prompt
from app.llm.fallback import generate_with_model_selection
from app.llm.router import get_router
from app.validation import validate_output

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def generate(
    prompt: str,
    agent_name: str | None = None,
    task_type: str | None = None,
    schema: type[T] | None = None,
    use_cache: bool = True,
    use_fallback: bool = True,
) -> str | T | None:
    """Generate content using the multi-model system.
    
    Args:
        prompt: The prompt to send to the LLM
        agent_name: Name of the agent (sdr, sales, negotiation, finance)
        task_type: Type of task (email_generation, sales_reasoning, etc.)
        schema: Optional Pydantic schema to validate output
        use_cache: Whether to use caching
        use_fallback: Whether to use fallback model on failure
        
    Returns:
        Raw string if schema is None, otherwise validated schema instance
    """
    # Get model for this request
    router = get_router()
    model = router.get_model_for_request(agent_name=agent_name, task_type=task_type)
    json_mode = schema is not None
    
    # Check cache
    if use_cache:
        cache_key = get_cache_key(prompt)
        from app.core.cache import get_from_cache
        cached = get_from_cache(cache_key)
        if cached:
            logger.info(
                "llm.facade.cache_hit",
                extra={"event": "llm.facade.cache_hit", "model": model},
            )
            if schema:
                return validate_output(schema, cached)
            return cached
    
    # Generate with fallback
    response = generate_with_model_selection(
        agent_name=agent_name,
        task_type=task_type,
        prompt=prompt,
        json_mode=json_mode,
        use_fallback=use_fallback,
    )
    
    # Cache successful responses
    if use_cache and response:
        from app.core.cache import set_cache
        set_cache(cache_key, response)
    
    # Validate if schema provided
    if schema and response:
        return validate_output(schema, response)
    
    return response


def generate_email(
    prompt: str,
    schema: type[T] | None = None,
    use_cache: bool = True,
) -> str | T | None:
    """Generate email content using Qwen.
    
    Args:
        prompt: The prompt for email generation
        schema: Optional schema to validate output
        use_cache: Whether to use caching
        
    Returns:
        Generated email content
    """
    return generate(
        prompt=prompt,
        agent_name="sdr",
        task_type="email_generation",
        schema=schema,
        use_cache=use_cache,
    )


def generate_strategy(
    prompt: str,
    schema: type[T] | None = None,
    use_cache: bool = True,
) -> str | T | None:
    """Generate strategy using DeepSeek (reasoning).
    
    Args:
        prompt: The prompt for strategy generation
        schema: Optional schema to validate output
        use_cache: Whether to use caching
        
    Returns:
        Generated strategy content
    """
    return generate(
        prompt=prompt,
        agent_name="sales",
        task_type="sales_reasoning",
        schema=schema,
        use_cache=use_cache,
    )


def generate_with_features(
    data: dict[str, Any],
    agent_name: str | None = None,
    task_type: str | None = None,
    schema: type[T] | None = None,
    use_cache: bool = True,
) -> str | T | None:
    """Generate content using feature-engineered input.
    
    This reduces prompt size by extracting relevant features
    before sending to the LLM.
    
    Args:
        data: Raw data dictionary
        agent_name: Agent name for routing
        task_type: Task type for routing
        schema: Optional schema to validate output
        use_cache: Whether to use caching
        
    Returns:
        Generated content
    """
    features = extract_features(data)
    prompt = features_to_prompt(features)
    
    return generate(
        prompt=prompt,
        agent_name=agent_name,
        task_type=task_type,
        schema=schema,
        use_cache=use_cache,
    )


# Convenience function for backward compatibility
def call_multi_model(
    prompt: str,
    agent_name: str | None = None,
    task_type: str | None = None,
    json_mode: bool = False,
) -> str:
    """Call multi-model LLM system (backward compatible interface).
    
    Args:
        prompt: The prompt to send
        agent_name: Agent name for routing
        task_type: Task type for routing
        json_mode: Whether to request JSON response
        
    Returns:
        LLM response string or empty string on failure
    """
    result = generate(
        prompt=prompt,
        agent_name=agent_name,
        task_type=task_type,
        schema=None,
        use_cache=False,
        use_fallback=True,
    )
    return result if result else ""
