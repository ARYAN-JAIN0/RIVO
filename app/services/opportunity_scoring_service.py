from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.services.llm_client import call_llm
from app.utils.validators import sanitize_text

logger = logging.getLogger(__name__)


@dataclass
class OpportunityScore:
    rule_score: int
    llm_score: int
    final_probability: float
    confidence: int
    breakdown: dict
    explanation: str


class OpportunityScoringService:
    """Hybrid opportunity probability model (0.6 rules + 0.4 LLM)."""

    @staticmethod
    def _rule_score(lead, email_log_count: int = 0) -> tuple[int, dict[str, int]]:
        role = sanitize_text(str(getattr(lead, "role", "")).lower())
        insight = sanitize_text(str(getattr(lead, "verified_insight", "")).lower())
        followups = int(getattr(lead, "followup_count", 0) or 0)

        budget = 20 if any(x in insight for x in ["budget", "approved", "funding"]) else 8
        authority = 20 if any(x in role for x in ["ceo", "cto", "cfo", "vp", "director", "head", "founder"]) else 10
        need = 20 if any(x in insight for x in ["urgent", "pain", "struggling", "migration", "risk"]) else 10
        timeline = 20 if any(x in insight for x in ["q", "quarter", "asap", "immediate", "this month"]) else 8
        engagement = min(20, (email_log_count * 4) + (max(0, 3 - followups) * 2))

        factors = {
            "budget_signal": budget,
            "authority_level": authority,
            "need_clarity": need,
            "timeline_urgency": timeline,
            "email_engagement": engagement,
            "followup_responsiveness": max(0, 20 - (followups * 5)),
        }
        total = min(100, int(round(sum(factors.values()) / 1.2)))
        return total, factors

    @staticmethod
    def _llm_score(lead, transcript: str = "") -> tuple[int, str]:
        prompt = f"""
You are a sales intelligence model. Return JSON only.
Analyze sentiment, buying intent, and objection intensity for this lead context.

Lead:
- company: {sanitize_text(str(getattr(lead, 'company', '')))}
- role: {sanitize_text(str(getattr(lead, 'role', '')))}
- insight: {sanitize_text(str(getattr(lead, 'verified_insight', '')))}
- transcript: {sanitize_text(transcript, 4000)}

JSON:
{{"llm_score": 0-100, "explanation": "short"}}
"""
        response = call_llm(prompt, json_mode=True).strip()
        if not response:
            return 50, "LLM unavailable; neutral probability applied"

        try:
            data = json.loads(response)
            score = int(data.get("llm_score", 50))
            return max(0, min(score, 100)), sanitize_text(str(data.get("explanation", "LLM-derived intent/objection score")), 1200)
        except (ValueError, TypeError, json.JSONDecodeError):
            logger.warning("opportunity.llm_parse_failed", extra={"event": "opportunity.llm_parse_failed"})
            return 50, "Invalid LLM payload; neutral score fallback"

    def score(self, lead, email_log_count: int = 0, transcript: str = "") -> OpportunityScore:
        rule_score, factors = self._rule_score(lead, email_log_count=email_log_count)
        llm_score, llm_explanation = self._llm_score(lead, transcript=transcript)
        final_probability = round((0.6 * rule_score) + (0.4 * llm_score), 2)
        confidence = int(round((rule_score * 0.5) + (llm_score * 0.5)))
        explanation = f"Rule={rule_score}, LLM={llm_score}. {llm_explanation}"

        return OpportunityScore(
            rule_score=rule_score,
            llm_score=llm_score,
            final_probability=final_probability,
            confidence=confidence,
            breakdown=factors,
            explanation=explanation,
        )
