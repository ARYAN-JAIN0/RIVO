"""Confidence scoring heuristics for LLM outputs."""

from __future__ import annotations


def estimate_confidence(text: str) -> int:
    """Estimate confidence using simple deterministic heuristics."""
    cleaned = text.strip()
    if not cleaned:
        return 0
    length_score = min(len(cleaned) // 4, 70)
    structure_bonus = 20 if "{" in cleaned and "}" in cleaned else 10
    certainty_bonus = 10 if len(cleaned.split()) >= 20 else 0
    return min(length_score + structure_bonus + certainty_bonus, 100)

