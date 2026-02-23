"""Pydantic schemas for strict LLM output validation."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


FORBIDDEN_PLACEHOLDER_TOKENS = (
    "[your name]",
    "[your company]",
    "{name}",
    "{company}",
    "[payment link]",
)


class SDREmailGeneration(BaseModel):
    thought_process: str = Field(min_length=5, max_length=2000)
    email_body: str = Field(min_length=30, max_length=1200)

    @field_validator("email_body")
    @classmethod
    def email_body_has_no_placeholders(cls, value: str) -> str:
        lowered = value.lower()
        for token in FORBIDDEN_PLACEHOLDER_TOKENS:
            if token in lowered:
                raise ValueError(f"placeholder token detected: {token}")
        return value


class SDREmailEvaluation(BaseModel):
    critique: str = Field(min_length=3, max_length=2000)
    score: int = Field(ge=0, le=100)


class DunningGeneration(BaseModel):
    email_body: str = Field(min_length=30, max_length=1200)
    confidence: int = Field(ge=0, le=100)


def parse_schema(model_cls: type[BaseModel], payload: str) -> BaseModel:
    """Validate JSON payload against a Pydantic model."""
    try:
        return model_cls.model_validate_json(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def safe_parse_json(payload: str, default: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    """Safely parse JSON from LLM response with fallback.
    
    Args:
        payload: Raw string potentially containing JSON
        default: Default value to return on parse failure (default: None)
    
    Returns:
        Parsed dict on success, default value on failure.
    
    Usage:
        data = safe_parse_json(llm_response, default={"score": 0, "reasoning": ""})
    """
    if not payload:
        return default
    
    try:
        return json.loads(payload.strip())
    except (json.JSONDecodeError, TypeError, AttributeError) as e:
        logger.warning(
            "schema.json_parse_failed",
            extra={"event": "schema.json_parse_failed", "error": str(e)},
        )
        return default

