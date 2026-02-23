from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict, field
from typing import List, Optional

from app.services.llm_client import call_llm
from app.utils.validators import sanitize_text

logger = logging.getLogger(__name__)


@dataclass
class DealExplanation:
    """Structured explanation for deal probability scoring.
    
    Contains deterministic analysis of deal strengths, risks, and recommendations.
    All text is generated from rule-based logic, not LLM calls.
    """
    probability: float
    confidence: str  # "High", "Medium", "Low"
    positive_factors: List[str] = field(default_factory=list)
    negative_factors: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    strategic_fit: str = "Not assessed"
    recommendation: str = "REVIEW"  # "APPROVE", "REVIEW", "REJECT"


@dataclass
class OpportunityScore:
    rule_score: int
    llm_score: int
    final_probability: float
    confidence: int
    breakdown: dict
    explanation: str
    deal_explanation: Optional[DealExplanation] = None


class OpportunityScoringService:
    """Hybrid opportunity probability model (0.6 rules + 0.4 LLM)."""

    # Thresholds for factor analysis
    BUDGET_HIGH_THRESHOLD = 15
    BUDGET_LOW_THRESHOLD = 10
    AUTHORITY_HIGH_THRESHOLD = 15
    AUTHORITY_LOW_THRESHOLD = 15
    NEED_HIGH_THRESHOLD = 15
    NEED_LOW_THRESHOLD = 10
    TIMELINE_HIGH_THRESHOLD = 15
    TIMELINE_LOW_THRESHOLD = 10
    ENGAGEMENT_HIGH_THRESHOLD = 15
    ENGAGEMENT_LOW_THRESHOLD = 8
    FOLLOWUP_LOW_THRESHOLD = 10
    
    # Probability thresholds for recommendations
    PROBABILITY_APPROVE_THRESHOLD = 75
    PROBABILITY_REVIEW_THRESHOLD = 50
    POSITIVE_FACTORS_REVIEW_THRESHOLD = 3
    
    # Margin threshold
    LOW_MARGIN_THRESHOLD = 0.20

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

    def _generate_explanation(
        self,
        breakdown: dict,
        final_probability: float,
        margin: float = 0.35,
        segment: str = "SMB"
    ) -> DealExplanation:
        """Generate structured explanation from scoring breakdown using deterministic rules.
        
        Args:
            breakdown: Factor scores from _rule_score()
            final_probability: Combined probability score
            margin: Deal margin (0.0 to 1.0)
            segment: Customer segment tag
            
        Returns:
            DealExplanation with strengths, risks, and recommendation
        """
        positive_factors: List[str] = []
        negative_factors: List[str] = []
        risk_flags: List[str] = []
        
        # Budget analysis
        budget_signal = breakdown.get("budget_signal", 0)
        if budget_signal >= self.BUDGET_HIGH_THRESHOLD:
            positive_factors.append("Budget signals detected - approved funding or budget allocated")
        elif budget_signal < self.BUDGET_LOW_THRESHOLD:
            negative_factors.append("Limited budget clarity - no confirmed budget")
        
        # Authority analysis
        authority_level = breakdown.get("authority_level", 0)
        if authority_level >= self.AUTHORITY_HIGH_THRESHOLD:
            positive_factors.append("Decision maker engaged - C-level or VP contact")
        elif authority_level < self.AUTHORITY_LOW_THRESHOLD:
            negative_factors.append("Non-decision maker contact - may require escalation")
        
        # Need analysis
        need_clarity = breakdown.get("need_clarity", 0)
        if need_clarity >= self.NEED_HIGH_THRESHOLD:
            positive_factors.append("Clear pain points identified - urgent need expressed")
        elif need_clarity < self.NEED_LOW_THRESHOLD:
            negative_factors.append("Unclear need - no explicit pain points")
        
        # Timeline analysis
        timeline_urgency = breakdown.get("timeline_urgency", 0)
        if timeline_urgency >= self.TIMELINE_HIGH_THRESHOLD:
            positive_factors.append("Active buying timeline - Q4 or immediate purchase intent")
        elif timeline_urgency < self.TIMELINE_LOW_THRESHOLD:
            negative_factors.append("Extended timeline - no urgency detected")
        
        # Engagement analysis
        email_engagement = breakdown.get("email_engagement", 0)
        if email_engagement >= self.ENGAGEMENT_HIGH_THRESHOLD:
            positive_factors.append("High engagement - multiple email interactions")
        elif email_engagement < self.ENGAGEMENT_LOW_THRESHOLD:
            negative_factors.append("Low engagement - minimal response activity")
        
        # Follow-up responsiveness
        followup_responsiveness = breakdown.get("followup_responsiveness", 0)
        if followup_responsiveness < self.FOLLOWUP_LOW_THRESHOLD:
            risk_flags.append("Slow follow-up response - may indicate low priority")
        
        # Margin risk
        if margin < self.LOW_MARGIN_THRESHOLD:
            risk_flags.append(f"Low margin deal - below {int(self.LOW_MARGIN_THRESHOLD * 100)}% threshold")
        
        # Determine confidence level
        if final_probability >= 75:
            confidence = "High"
        elif final_probability >= 50:
            confidence = "Medium"
        else:
            confidence = "Low"
        
        # Determine strategic fit
        strategic_fit = self._determine_strategic_fit(segment, positive_factors, risk_flags)
        
        # Determine recommendation
        recommendation = self._determine_recommendation(final_probability, risk_flags, positive_factors)
        
        return DealExplanation(
            probability=final_probability,
            confidence=confidence,
            positive_factors=positive_factors,
            negative_factors=negative_factors,
            risk_flags=risk_flags,
            strategic_fit=strategic_fit,
            recommendation=recommendation
        )

    def _determine_strategic_fit(
        self,
        segment: str,
        positive_factors: List[str],
        risk_flags: List[str]
    ) -> str:
        """Determine strategic fit description based on segment and factors."""
        if segment == "Enterprise":
            if len(positive_factors) >= 3 and len(risk_flags) == 0:
                return "High-value enterprise opportunity with strong buying signals"
            elif len(risk_flags) > 0:
                return "Enterprise opportunity with risk factors requiring attention"
            else:
                return "Enterprise opportunity with moderate buying signals"
        elif segment == "High Intent":
            return "High-intent prospect showing active buying behavior"
        elif segment == "Strategic":
            return "Strategic account with potential for long-term partnership"
        elif segment == "Price Sensitive":
            if len(risk_flags) > 0:
                return "Price-sensitive prospect with margin concerns"
            else:
                return "Price-sensitive prospect requiring value-focused approach"
        else:  # SMB
            if len(positive_factors) >= 3:
                return "Strong SMB opportunity with clear buying signals"
            elif len(positive_factors) >= 1:
                return "SMB opportunity with some positive indicators"
            else:
                return "SMB opportunity requiring further qualification"
    
    def _determine_recommendation(
        self,
        final_probability: float,
        risk_flags: List[str],
        positive_factors: List[str]
    ) -> str:
        """Determine system recommendation based on probability and factors."""
        if final_probability >= self.PROBABILITY_APPROVE_THRESHOLD and len(risk_flags) == 0:
            return "APPROVE"
        elif final_probability >= self.PROBABILITY_REVIEW_THRESHOLD or len(positive_factors) >= self.POSITIVE_FACTORS_REVIEW_THRESHOLD:
            return "REVIEW"
        else:
            return "REJECT"

    def score(
        self,
        lead,
        email_log_count: int = 0,
        transcript: str = "",
        margin: float = 0.35,
        segment: str = "SMB"
    ) -> OpportunityScore:
        """Score a lead and generate structured explanation.
        
        Args:
            lead: Lead object with role, company, verified_insight attributes
            email_log_count: Number of email interactions
            transcript: Call/meeting transcript for LLM analysis
            margin: Deal margin (0.0 to 1.0), default 0.35
            segment: Customer segment tag, default "SMB"
            
        Returns:
            OpportunityScore with breakdown and structured deal_explanation
        """
        rule_score, factors = self._rule_score(lead, email_log_count=email_log_count)
        llm_score, llm_explanation = self._llm_score(lead, transcript=transcript)
        final_probability = round((0.6 * rule_score) + (0.4 * llm_score), 2)
        confidence = int(round((rule_score * 0.5) + (llm_score * 0.5)))
        explanation = f"Rule={rule_score}, LLM={llm_score}. {llm_explanation}"

        # Generate structured explanation
        deal_explanation = self._generate_explanation(
            breakdown=factors,
            final_probability=final_probability,
            margin=margin,
            segment=segment
        )

        return OpportunityScore(
            rule_score=rule_score,
            llm_score=llm_score,
            final_probability=final_probability,
            confidence=confidence,
            breakdown=factors,
            explanation=explanation,
            deal_explanation=deal_explanation
        )

    @staticmethod
    def deal_explanation_to_dict(explanation: DealExplanation) -> dict:
        """Convert DealExplanation to dictionary for JSON storage.
        
        Args:
            explanation: DealExplanation dataclass instance
            
        Returns:
            Dictionary suitable for JSON storage in Deal.probability_breakdown
        """
        return asdict(explanation)
