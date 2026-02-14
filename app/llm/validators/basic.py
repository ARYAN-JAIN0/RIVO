"""Deterministic output validators used by LLM orchestration."""

from __future__ import annotations


def validate_non_empty_output(text: str) -> tuple[bool, str | None]:
    if text and text.strip():
        return True, None
    return False, "Output is empty."

