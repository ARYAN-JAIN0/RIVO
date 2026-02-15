"""Deterministic validators and sanitizers used across agents and UI."""

from __future__ import annotations

import html
import re

FORBIDDEN_TOKENS = (
    "[your name]",
    "[your company]",
    "[your position]",
    "[contact information]",
    "[specific date]",
    "[time]",
    "{name}",
    "{company}",
)


def sanitize_text(value: str | None, max_len: int = 20000) -> str:
    """Sanitize free-form content before persistence/display."""
    if value is None:
        return ""
    cleaned = str(value).replace("\x00", "").strip()
    cleaned = cleaned[:max_len]
    return cleaned


def sanitize_llm_output(value: str | None, max_len: int = 20000) -> str:
    """Escape LLM output before rendering in web surfaces."""
    return html.escape(sanitize_text(value, max_len=max_len))


def contains_forbidden_tokens(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in FORBIDDEN_TOKENS)


def validate_structure(email_text: str) -> bool:
    """
    Deterministic structural validation.
    No LLM calls. No scoring. Pure rules.
    """
    if not email_text or not isinstance(email_text, str):
        return False

    text = sanitize_text(email_text)
    if not text:
        return False

    valid_greetings = ("hi ", "hello ", "dear ")
    if not text.lower().startswith(valid_greetings):
        return False

    if contains_forbidden_tokens(text):
        return False

    valid_signoffs = ("best,", "best regards,", "regards,", "thanks,", "thank you,")
    lowered = text.lower().rstrip()
    if not any(lowered.endswith(signoff) for signoff in valid_signoffs):
        tail = "\n".join(lowered.splitlines()[-4:])
        has_signoff_block = any(signoff in tail for signoff in valid_signoffs)
        # Accept signed emails that end with an email address.
        if not has_signoff_block and not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", lowered):
            return False

    if len(text.split()) < 30:
        return False

    return True


def deterministic_email_quality_score(email_text: str, company: str = "", industry: str = "") -> int:
    """Deterministic quality score to reduce single-model self-evaluation bias."""
    text = sanitize_text(email_text).lower()
    score = 40

    if validate_structure(email_text):
        score += 20
    if company and company.lower() in text:
        score += 15
    if industry and industry.lower() in text:
        score += 10
    if "?" in text:
        score += 5
    if len(text.split()) >= 45:
        score += 5
    if contains_forbidden_tokens(text):
        score -= 30

    return max(0, min(score, 100))
