"""Pydantic schemas for strict LLM output validation."""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError, field_validator


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

