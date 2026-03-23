"""Objection classification layer with rule-based classification and LLM fallback.

Classification types:
- PRICE: Price, cost, budget objections
- TIMING: Timeline, urgency, "too busy" objections  
- AUTHORITY: Need approval, not decision maker
- VALUE: ROI, value proposition concerns

This module follows the LLM separation rule:
- Rule-based classification is the priority path (deterministic)
- LLM is used ONLY when rules fail to classify
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.services.llm_client import call_llm

logger = logging.getLogger(__name__)


# Rule-based classification patterns
CLASSIFICATION_PATTERNS = {
    "PRICE": {
        "keywords": [
            "expensive", "cost", "price", "budget", "afford", "cheaper",
            "discount", "reduce", "lower", "savings", "value", "roi",
            "money", "payment", "terms", "licens", "fee", "overpriced",
        ],
        "weight": 1.0,
    },
    "TIMING": {
        "keywords": [
            "time", "busy", "later", "next quarter", "delay", "soon",
            "immediate", "now", "later", "timeline", "deadline", "schedule",
            "bandwidth", "capacity", "backlog", "fiscal", "quarter", "year",
        ],
        "weight": 1.0,
    },
    "AUTHORITY": {
        "keywords": [
            "approval", "approve", "decision", "decision maker", "team",
            "committee", "board", "boss", "manager", "supervisor", "lead",
            "need to", "have to", "must", "requires", "concurrenc",
            "sign off", "sign-off", "buy in", "buy-in", "stakeholder",
        ],
        "weight": 1.0,
    },
    "VALUE": {
        "keywords": [
            "prove", "proven", "case study", "reference", "risk", "trust",
            "reliable", "experience", "track record", "results", "outcome",
            "benefit", "impact", "problem", "solution", "different",
            "competitor", "alternative", "comparison", "better", "best",
        ],
        "weight": 0.8,  # Lower weight as these are more ambiguous
    },
}


@dataclass
class ClassificationResult:
    """Result of objection classification."""
    objection_type: str  # PRICE, TIMING, AUTHORITY, VALUE
    confidence: float  # 0-1 confidence score
    method: str  # "rule_based" or "llm_fallback"
    raw_input: str  # Original input for debugging


def _rule_based_classify(text: str) -> tuple[str, float] | None:
    """Classify objection using rule-based patterns.
    
    Args:
        text: The objection text to classify.
        
    Returns:
        Tuple of (objection_type, confidence) or None if no match.
    """
    text_lower = text.lower()
    scores: dict[str, float] = {}
    
    for obj_type, config in CLASSIFICATION_PATTERNS.items():
        matches = sum(1 for kw in config["keywords"] if kw in text_lower)
        if matches > 0:
            # Weight by number of matches and pattern weight
            scores[obj_type] = matches * config["weight"]
    
    if not scores:
        return None
    
    # Return the type with highest score
    best_type = max(scores, key=scores.get)
    max_score = scores[best_type]
    
    # Normalize confidence to 0-1 range (cap at 1.0)
    confidence = min(max_score / 3.0, 1.0)
    
    return best_type, confidence


def _llm_classify(text: str, context: dict | None = None) -> tuple[str, float]:
    """Classify objection using LLM when rules fail.
    
    Args:
        text: The objection text to classify.
        context: Optional deal context for better classification.
        
    Returns:
        Tuple of (objection_type, confidence).
    """
    company_info = ""
    if context:
        company = context.get("company", "")
        deal_value = context.get("deal_value", 0)
        if company:
            company_info = f"\nCompany: {company}\nDeal Value: ${deal_value:,}"
    
    prompt = f"""Classify this sales objection into one of these categories:
- PRICE: Price, cost, budget, affordability concerns
- TIMING: Timeline, urgency, scheduling concerns
- AUTHORITY: Need approval, not decision maker, team buy-in
- VALUE: ROI, value proposition, trust, proof concerns

Objection: {text}{company_info}

Output JSON only:
{{
  "category": "PRICE|TIMING|AUTHORITY|VALUE",
  "confidence": 0.0-1.0
}}"""
    
    response = call_llm(prompt, json_mode=True)
    
    if response:
        try:
            data = json.loads(response)
            category = data.get("category", "").strip().upper()
            confidence = float(data.get("confidence", 0.5))
            
            if category in CLASSIFICATION_PATTERNS and 0 <= confidence <= 1:
                logger.info(
                    "negotiation.classification.llm_success",
                    extra={
                        "event": "negotiation.classification.llm_success",
                        "category": category,
                        "confidence": confidence,
                    },
                )
                return category, confidence
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(
                "negotiation.classification.llm_parse_failed",
                extra={
                    "event": "negotiation.classification.llm_parse_failed",
                    "error": str(e),
                },
            )
    
    # Fallback to default
    logger.warning(
        "negotiation.classification.llm_failed",
        extra={
            "event": "negotiation.classification.llm_failed",
            "fallback": "VALUE",
        },
    )
    return "VALUE", 0.3


def classify_objection(
    text: str,
    context: dict | None = None,
) -> ClassificationResult:
    """Classify an objection using rule-based patterns with LLM fallback.
    
    This function implements the classification layer:
    1. First attempts rule-based classification (deterministic, fast)
    2. Falls back to LLM classification if rules don't produce confident result
    3. Returns structured ClassificationResult
    
    Args:
        text: The objection text to classify.
        context: Optional deal context (company, deal_value) for LLM fallback.
        
    Returns:
        ClassificationResult with type, confidence, and method used.
    """
    if not text or not text.strip():
        logger.warning(
            "negotiation.classification.empty_input",
            extra={"event": "negotiation.classification.empty_input"},
        )
        return ClassificationResult(
            objection_type="VALUE",
            confidence=0.0,
            method="empty_input",
            raw_input=text or "",
        )
    
    # Try rule-based classification first
    rule_result = _rule_based_classify(text)
    
    if rule_result:
        objection_type, confidence = rule_result
        
        # If confidence is high enough (>0.5), use rule-based result
        if confidence >= 0.5:
            logger.info(
                "negotiation.classification.rule_based",
                extra={
                    "event": "negotiation.classification.rule_based",
                    "objection_type": objection_type,
                    "confidence": confidence,
                },
            )
            return ClassificationResult(
                objection_type=objection_type,
                confidence=confidence,
                method="rule_based",
                raw_input=text,
            )
    
    # Fall back to LLM classification
    objection_type, confidence = _llm_classify(text, context)
    
    return ClassificationResult(
        objection_type=objection_type,
        confidence=confidence,
        method="llm_fallback",
        raw_input=text,
    )
