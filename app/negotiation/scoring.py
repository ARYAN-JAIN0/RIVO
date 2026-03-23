"""Scoring layer for negotiation responses.

This module scores generated responses on:
- Strategy alignment: Does response follow the selected strategy?
- Relevance: Does response address the objection?
- Coherence: Is the response grammatically correct and logical?

Flag for human review if score < 75.

This is a deterministic system component (no LLM involved).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Scoring thresholds
HUMAN_REVIEW_THRESHOLD = 75

# Strategy keywords for alignment scoring
STRATEGY_KEYWORDS = {
    "DISCOUNT": [
        "discount", "price", "cost", "budget", "afford", "saving",
        "reduce", "lower", "flexible", "agreement", "annual", "commit",
    ],
    "VALUE_REINFORCEMENT": [
        "value", "roi", "return", "benefit", "case study", "similar",
        "companies", "industry", "results", "outcome", "impact",
    ],
    "URGENCY": [
        "now", "today", "deadline", "limited", "time", "soon",
        "window", "ending", "available", "until", "act", "fast",
    ],
    "DEFERRAL": {
        "understand", "follow", "schedule", "reconnect", "when", "clarity",
        "prepare", "materials", "meeting", "decision", "stakeholder",
    },
}


@dataclass
class ScoringResult:
    """Result of response scoring."""
    total_score: int  # 0-100
    strategy_alignment: int  # 0-100
    relevance: int  # 0-100
    coherence: int  # 0-100
    requires_human_review: bool
    issues: list[str]


def _score_strategy_alignment(response: str, strategy: str) -> int:
    """Score how well the response aligns with the selected strategy.
    
    Args:
        response: The generated response.
        strategy: The selected strategy.
        
    Returns:
        Score 0-100.
    """
    response_lower = response.lower()
    keywords = STRATEGY_KEYWORDS.get(strategy, [])
    
    if not keywords:
        return 50  # Default if no keywords defined
    
    matches = sum(1 for kw in keywords if kw in response_lower)
    max_expected = min(len(keywords), 5)  # Cap at 5 keywords
    
    # Score based on keyword presence
    score = int((matches / max_expected) * 100)
    return min(score, 100)


def _score_relevance(response: str, objection: str) -> int:
    """Score how relevant the response is to the objection.
    
    Args:
        response: The generated response.
        objection: The original objection.
        
    Returns:
        Score 0-100.
    """
    objection_lower = objection.lower()
    response_lower = response.lower()
    
    # Extract key words from objection (exclude common words)
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "being", "have", "has", "had", "do", "does", "did", "will",
                  "would", "could", "should", "may", "might", "must", "shall",
                  "can", "need", "dare", "ought", "used", "to", "of", "in",
                  "for", "on", "with", "at", "by", "from", "as", "into",
                  "through", "during", "before", "after", "above", "below",
                  "between", "under", "again", "further", "then", "once", "i",
                  "we", "you", "they", "he", "she", "it", "my", "your", "their"}
    
    objection_words = set(word.strip(".,!?") for word in objection_lower.split())
    objection_words = objection_words - stop_words
    
    if not objection_words:
        return 70  # Default if no meaningful objection words
    
    # Check how many objection words are addressed in response
    # This is a proxy - we're checking if response acknowledges the concern
    addressed = sum(1 for word in objection_words if word in response_lower)
    
    score = int((addressed / len(objection_words)) * 100)
    
    # Penalize if response is too short
    if len(response.split()) < 10:
        score = min(score, 60)
    elif len(response.split()) < 20:
        score = min(score, 80)
    
    return min(score, 100)


def _score_coherence(response: str) -> int:
    """Score the coherence of the response.
    
    Args:
        response: The generated response.
        
    Returns:
        Score 0-100.
    """
    # Check for basic coherence indicators
    score = 100
    
    # Penalize if too short
    if len(response.split()) < 5:
        return 30
    
    # Penalize if too long
    if len(response.split()) > 100:
        return 60
    
    # Check for sentence structure (basic check)
    sentences = re.split(r"[.!?]+", response)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return 20
    
    # Check for complete sentences (at least one sentence with 5+ words)
    has_complete = any(len(s.split()) >= 5 for s in sentences)
    if not has_complete:
        score -= 30
    
    # Check for repeated words (sign of poor coherence)
    words = response.lower().split()
    if len(words) > 10:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.3:
            score -= 40
    
    # Check for placeholder tokens
    placeholders = ["[", "]", "{", "}", "...", "xxx", "example"]
    has_placeholder = any(p in response for p in placeholders)
    if has_placeholder:
        score -= 50
    
    return max(score, 0)


def score_response(
    response: str,
    objection: str,
    strategy: str,
) -> ScoringResult:
    """Score a generated negotiation response.
    
    This function implements the scoring layer:
    1. Scores strategy alignment (0-100)
    2. Scores relevance to objection (0-100)
    3. Scores coherence (0-100)
    4. Computes weighted total
    5. Flags for human review if total < 75
    
    Args:
        response: The generated response to score.
        objection: The original objection.
        strategy: The selected strategy.
        
    Returns:
        ScoringResult with all scores and human review flag.
    """
    if not response or not response.strip():
        logger.warning(
            "negotiation.scoring.empty_response",
            extra={"event": "negotiation.scoring.empty_response"},
        )
        return ScoringResult(
            total_score=0,
            strategy_alignment=0,
            relevance=0,
            coherence=0,
            requires_human_review=True,
            issues=["Empty response"],
        )
    
    # Calculate individual scores
    strategy_score = _score_strategy_alignment(response, strategy)
    relevance_score = _score_relevance(response, objection)
    coherence_score = _score_coherence(response)
    
    # Weighted total (strategy alignment is most important)
    total = int(strategy_score * 0.4 + relevance_score * 0.35 + coherence_score * 0.25)
    
    # Determine issues
    issues = []
    if strategy_score < 50:
        issues.append(f"Low strategy alignment ({strategy_score})")
    if relevance_score < 50:
        issues.append(f"Low relevance to objection ({relevance_score})")
    if coherence_score < 50:
        issues.append(f"Low coherence ({coherence_score})")
    
    requires_review = total < HUMAN_REVIEW_THRESHOLD or len(issues) >= 2
    
    if requires_review:
        logger.warning(
            "negotiation.scoring.requires_review",
            extra={
                "event": "negotiation.scoring.requires_review",
                "total_score": total,
                "strategy_score": strategy_score,
                "relevance_score": relevance_score,
                "coherence_score": coherence_score,
                "issues": issues,
            },
        )
    else:
        logger.info(
            "negotiation.scoring.passed",
            extra={
                "event": "negotiation.scoring.passed",
                "total_score": total,
            },
        )
    
    return ScoringResult(
        total_score=total,
        strategy_alignment=strategy_score,
        relevance=relevance_score,
        coherence=coherence_score,
        requires_human_review=requires_review,
        issues=issues,
    )
