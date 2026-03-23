"""Negotiation package for stateful multi-turn negotiation system.

This package provides:
- Classification: Rule-based objection classification with LLM fallback
- Strategy: Strategy selection engine
- Generation: LLM response generation with fallback
- Scoring: Response quality scoring
- Contract updates: Price and timeline adjustments

All components follow the RIVO architecture principles:
- LLM → generation ONLY
- System → validation, scoring, decisions
- Strict separation of concerns
"""

from app.negotiation.classification import classify_objection
from app.negotiation.strategy import select_strategy
from app.negotiation.generation import generate_response
from app.negotiation.scoring import score_response

__all__ = [
    "classify_objection",
    "select_strategy",
    "generate_response",
    "score_response",
]
