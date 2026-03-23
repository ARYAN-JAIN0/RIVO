"""Validation utilities for LLM outputs."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from pydantic import BaseModel

from app.schemas.llm_outputs import LLM_OUTPUT_SCHEMAS

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def validate_output(schema: type[T], raw_output: str) -> T | None:
    """Validate raw LLM output against a Pydantic schema.
    
    Args:
        schema: Pydantic BaseModel class to validate against
        raw_output: Raw string output from LLM
        
    Returns:
        Validated Pydantic model instance, or None if validation fails
    """
    if not raw_output or not raw_output.strip():
        logger.warning(
            "validation.empty_output",
            extra={"event": "validation.empty_output", "schema": schema.__name__},
        )
        return None

    try:
        # Handle both JSON string and plain text responses
        output = raw_output.strip()
        
        # Try to parse as JSON if schema expects it
        if schema in LLM_OUTPUT_SCHEMAS.values():
            return schema.model_validate_json(output)
        
        return schema.model_validate_json(output)
    except Exception as exc:
        logger.warning(
            "validation.failed",
            extra={
                "event": "validation.failed",
                "schema": schema.__name__,
                "error": str(exc),
                "output_preview": output[:200] if len(output) > 200 else output,
            },
        )
        return None


def validate_output_by_name(schema_name: str, raw_output: str) -> BaseModel | None:
    """Validate output using a schema name.
    
    Args:
        schema_name: Name of the schema (email, strategy, negotiation, etc.)
        raw_output: Raw string output from LLM
        
    Returns:
        Validated Pydantic model instance, or None if validation fails
    """
    schema = LLM_OUTPUT_SCHEMAS.get(schema_name)
    if schema is None:
        logger.error(
            "validation.unknown_schema",
            extra={"event": "validation.unknown_schema", "schema_name": schema_name},
        )
        return None
    
    return validate_output(schema, raw_output)


def safe_validate(schema: type[T], raw_output: str, default: T | None = None) -> T | None:
    """Validate output with a fallback default.
    
    Args:
        schema: Pydantic BaseModel class
        raw_output: Raw string output from LLM
        default: Default value if validation fails
        
    Returns:
        Validated model or default value
    """
    result = validate_output(schema, raw_output)
    return result if result is not None else default
