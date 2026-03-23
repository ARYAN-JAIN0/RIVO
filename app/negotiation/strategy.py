"""Strategy selection layer for negotiation responses.

This module implements the strategy selection engine that maps objection types
to appropriate negotiation strategies. It is a deterministic system component
(no LLM involved in strategy selection).

Allowed strategies:
- DISCOUNT: Offer price reduction or special pricing
- VALUE_REINFORCEMENT: Emphasize ROI and value proposition
- URGENCY: Create time-based motivation
- DEFERRAL: Defer decision to future with rationale

Strategy selection rules:
- PRICE → DISCOUNT or VALUE_REINFORCEMENT
- TIMING → URGENCY or DEFERRAL
- AUTHORITY → DEFERRAL
- VALUE → VALUE_REINFORCEMENT

The system also avoids repeating the same strategy consecutively.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from random import choice

logger = logging.getLogger(__name__)


# Strategy definitions
class Strategy(str):
    """Available negotiation strategies."""
    DISCOUNT = "DISCOUNT"
    VALUE_REINFORCEMENT = "VALUE_REINFORCEMENT"
    URGENCY = "URGENCY"
    DEFERRAL = "DEFERRAL"


# Mapping from objection types to allowed strategies
OBJECTION_STRATEGY_MAP = {
    "PRICE": [Strategy.DISCOUNT, Strategy.VALUE_REINFORCEMENT],
    "TIMING": [Strategy.URGENCY, Strategy.DEFERRAL],
    "AUTHORITY": [Strategy.DEFERRAL],
    "VALUE": [Strategy.VALUE_REINFORCEMENT],
}


# Strategy templates for fallback
STRATEGY_TEMPLATES = {
    Strategy.DISCOUNT: [
        "We can offer a {discount}% discount for annual payment.",
        "Let me discuss some pricing options that might work for your budget.",
        "We have flexibility on pricing for committed annual agreements.",
    ],
    Strategy.VALUE_REINFORCEMENT: [
        "Based on similar implementations, customers typically see {roi}% ROI within the first year.",
        "The value extends beyond just the core features - including {benefit}.",
        "Let me share case studies from companies similar to yours that achieved {outcome}.",
    ],
    Strategy.URGENCY: [
        "This pricing is valid until {date}. After that, we'll be adjusting our rates.",
        "Given your timeline, starting now would allow you to capture {benefit} before year-end.",
        "The Q4 implementation window is filling up quickly - securing your spot now has advantages.",
    ],
    Strategy.DEFERRAL: [
        "I understand. Let's schedule a follow-up for when you have more clarity on the decision timeline.",
        "Would it be helpful to prepare some materials for your internal stakeholder meeting?",
        "Let's plan to reconnect once you have the necessary approvals.",
    ],
}


@dataclass
class StrategyResult:
    """Result of strategy selection."""
    strategy: str
    reason: str
    previous_strategy: str | None


def select_strategy(
    objection_type: str,
    deal_context: dict | None = None,
    previous_strategy: str | None = None,
) -> StrategyResult:
    """Select the appropriate negotiation strategy based on objection type.
    
    This function implements the deterministic strategy selection:
    1. Maps objection type to allowed strategies
    2. Avoids repeating the same strategy consecutively
    3. Considers deal context for strategy selection
    
    Args:
        objection_type: The classified objection type (PRICE, TIMING, AUTHORITY, VALUE)
        deal_context: Optional deal info (deal_value, company, etc.)
        previous_strategy: The previous strategy used (to avoid repetition)
        
    Returns:
        StrategyResult with selected strategy and reason
    """
    # Normalize objection type
    obj_type = objection_type.upper().strip()
    
    # Get allowed strategies for this objection type
    allowed_strategies = OBJECTION_STRATEGY_MAP.get(obj_type, [Strategy.VALUE_REINFORCEMENT])
    
    # Filter out previous strategy to avoid repetition
    available_strategies = [s for s in allowed_strategies if s != previous_strategy]
    
    # If all strategies filtered out, allow the previous one
    if not available_strategies:
        available_strategies = allowed_strategies
    
    # Select strategy (random among available for variety)
    selected = choice(available_strategies)
    
    # Generate reason
    deal_value = deal_context.get("deal_value", 0) if deal_context else 0
    company = deal_context.get("company", "") if deal_context else ""
    
    reason = f"Strategy '{selected}' selected for objection type '{obj_type}'"
    if company:
        reason += f" for {company}"
    if deal_value:
        reason += f" (deal value: ${deal_value:,})"
    
    logger.info(
        "negotiation.strategy.selected",
        extra={
            "event": "negotiation.strategy.selected",
            "objection_type": obj_type,
            "selected_strategy": selected,
            "previous_strategy": previous_strategy,
            "available_strategies": available_strategies,
        },
    )
    
    return StrategyResult(
        strategy=selected,
        reason=reason,
        previous_strategy=previous_strategy,
    )


def get_strategy_template(strategy: str) -> str:
    """Get a template response for the given strategy.
    
    Args:
        strategy: The selected strategy
        
    Returns:
        A template string for the strategy
    """
    templates = STRATEGY_TEMPLATES.get(strategy, STRATEGY_TEMPLATES[Strategy.VALUE_REINFORCEMENT])
    return choice(templates)
