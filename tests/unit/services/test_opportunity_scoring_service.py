"""Unit tests for OpportunityScoringService deal explanation generation."""

import pytest

from app.services.opportunity_scoring_service import (
    DealExplanation,
    OpportunityScore,
    OpportunityScoringService,
)


class TestDealExplanationDataclass:
    """Tests for DealExplanation dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        explanation = DealExplanation(probability=50.0, confidence="Medium")
        assert explanation.probability == 50.0
        assert explanation.confidence == "Medium"
        assert explanation.positive_factors == []
        assert explanation.negative_factors == []
        assert explanation.risk_flags == []
        assert explanation.strategic_fit == "Not assessed"
        assert explanation.recommendation == "REVIEW"

    def test_custom_values(self):
        """Test custom values are set correctly."""
        explanation = DealExplanation(
            probability=85.0,
            confidence="High",
            positive_factors=["Strong budget", "Decision maker engaged"],
            negative_factors=["Long timeline"],
            risk_flags=["Low margin"],
            strategic_fit="High-value enterprise opportunity",
            recommendation="APPROVE"
        )
        assert explanation.probability == 85.0
        assert explanation.confidence == "High"
        assert len(explanation.positive_factors) == 2
        assert len(explanation.negative_factors) == 1
        assert len(explanation.risk_flags) == 1
        assert explanation.recommendation == "APPROVE"


class TestGenerateExplanation:
    """Tests for _generate_explanation method."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return OpportunityScoringService()

    def test_high_probability_approve_recommendation(self, service):
        """Test APPROVE recommendation for high probability with no risks."""
        breakdown = {
            "budget_signal": 20,
            "authority_level": 20,
            "need_clarity": 20,
            "timeline_urgency": 20,
            "email_engagement": 20,
            "followup_responsiveness": 20,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=85.0,
            margin=0.35,
            segment="Enterprise"
        )
        
        assert explanation.probability == 85.0
        assert explanation.confidence == "High"
        assert explanation.recommendation == "APPROVE"
        assert len(explanation.positive_factors) >= 4
        assert len(explanation.risk_flags) == 0

    def test_medium_probability_review_recommendation(self, service):
        """Test REVIEW recommendation for medium probability."""
        breakdown = {
            "budget_signal": 15,
            "authority_level": 10,
            "need_clarity": 15,
            "timeline_urgency": 8,
            "email_engagement": 10,
            "followup_responsiveness": 15,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=55.0,
            margin=0.35,
            segment="SMB"
        )
        
        assert explanation.probability == 55.0
        assert explanation.confidence == "Medium"
        assert explanation.recommendation == "REVIEW"

    def test_low_probability_reject_recommendation(self, service):
        """Test REJECT recommendation for low probability."""
        breakdown = {
            "budget_signal": 8,
            "authority_level": 10,
            "need_clarity": 10,
            "timeline_urgency": 8,
            "email_engagement": 8,
            "followup_responsiveness": 5,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=35.0,
            margin=0.35,
            segment="SMB"
        )
        
        assert explanation.probability == 35.0
        assert explanation.confidence == "Low"
        assert explanation.recommendation == "REJECT"

    def test_low_margin_risk_flag(self, service):
        """Test low margin creates risk flag."""
        breakdown = {
            "budget_signal": 20,
            "authority_level": 20,
            "need_clarity": 20,
            "timeline_urgency": 20,
            "email_engagement": 20,
            "followup_responsiveness": 20,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=85.0,
            margin=0.15,  # Below 20% threshold
            segment="Enterprise"
        )
        
        assert len(explanation.risk_flags) == 1
        assert "Low margin" in explanation.risk_flags[0]
        # Should be REVIEW because of risk flag
        assert explanation.recommendation == "REVIEW"

    def test_budget_signal_positive_factor(self, service):
        """Test high budget signal creates positive factor."""
        breakdown = {
            "budget_signal": 20,  # High budget signal
            "authority_level": 10,
            "need_clarity": 10,
            "timeline_urgency": 8,
            "email_engagement": 10,
            "followup_responsiveness": 15,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=50.0,
            margin=0.35,
            segment="SMB"
        )
        
        budget_positive = any("Budget signals" in f for f in explanation.positive_factors)
        assert budget_positive

    def test_budget_signal_negative_factor(self, service):
        """Test low budget signal creates negative factor."""
        breakdown = {
            "budget_signal": 8,  # Low budget signal
            "authority_level": 10,
            "need_clarity": 10,
            "timeline_urgency": 8,
            "email_engagement": 10,
            "followup_responsiveness": 15,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=50.0,
            margin=0.35,
            segment="SMB"
        )
        
        budget_negative = any("Limited budget clarity" in f for f in explanation.negative_factors)
        assert budget_negative

    def test_authority_level_positive_factor(self, service):
        """Test high authority level creates positive factor."""
        breakdown = {
            "budget_signal": 10,
            "authority_level": 20,  # Decision maker
            "need_clarity": 10,
            "timeline_urgency": 8,
            "email_engagement": 10,
            "followup_responsiveness": 15,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=50.0,
            margin=0.35,
            segment="SMB"
        )
        
        authority_positive = any("Decision maker" in f for f in explanation.positive_factors)
        assert authority_positive

    def test_need_clarity_positive_factor(self, service):
        """Test high need clarity creates positive factor."""
        breakdown = {
            "budget_signal": 10,
            "authority_level": 10,
            "need_clarity": 20,  # Clear pain points
            "timeline_urgency": 8,
            "email_engagement": 10,
            "followup_responsiveness": 15,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=50.0,
            margin=0.35,
            segment="SMB"
        )
        
        need_positive = any("pain points" in f for f in explanation.positive_factors)
        assert need_positive

    def test_need_clarity_negative_factor(self, service):
        """Test low need clarity creates negative factor."""
        breakdown = {
            "budget_signal": 10,
            "authority_level": 10,
            "need_clarity": 10,  # No strong need signals
            "timeline_urgency": 8,
            "email_engagement": 10,
            "followup_responsiveness": 15,
        }

        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=50.0,
            margin=0.35,
            segment="SMB"
        )

        need_negative = any("Unclear need" in f for f in explanation.negative_factors)
        assert need_negative

    def test_timeline_urgency_positive_factor(self, service):
        """Test high timeline urgency creates positive factor."""
        breakdown = {
            "budget_signal": 10,
            "authority_level": 10,
            "need_clarity": 10,
            "timeline_urgency": 20,  # Active timeline
            "email_engagement": 10,
            "followup_responsiveness": 15,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=50.0,
            margin=0.35,
            segment="SMB"
        )
        
        timeline_positive = any("buying timeline" in f for f in explanation.positive_factors)
        assert timeline_positive

    def test_engagement_positive_factor(self, service):
        """Test high engagement creates positive factor."""
        breakdown = {
            "budget_signal": 10,
            "authority_level": 10,
            "need_clarity": 10,
            "timeline_urgency": 8,
            "email_engagement": 20,  # High engagement
            "followup_responsiveness": 15,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=50.0,
            margin=0.35,
            segment="SMB"
        )
        
        engagement_positive = any("engagement" in f for f in explanation.positive_factors)
        assert engagement_positive

    def test_followup_risk_flag(self, service):
        """Test low followup responsiveness creates risk flag."""
        breakdown = {
            "budget_signal": 20,
            "authority_level": 20,
            "need_clarity": 20,
            "timeline_urgency": 20,
            "email_engagement": 20,
            "followup_responsiveness": 5,  # Low responsiveness
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=85.0,
            margin=0.35,
            segment="Enterprise"
        )
        
        followup_risk = any("follow-up" in f for f in explanation.risk_flags)
        assert followup_risk

    def test_enterprise_segment_strategic_fit(self, service):
        """Test Enterprise segment strategic fit description."""
        breakdown = {
            "budget_signal": 20,
            "authority_level": 20,
            "need_clarity": 20,
            "timeline_urgency": 20,
            "email_engagement": 20,
            "followup_responsiveness": 20,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=85.0,
            margin=0.35,
            segment="Enterprise"
        )
        
        # Check for enterprise (case-insensitive)
        assert "enterprise" in explanation.strategic_fit.lower()

    def test_high_intent_segment_strategic_fit(self, service):
        """Test High Intent segment strategic fit description."""
        breakdown = {
            "budget_signal": 15,
            "authority_level": 15,
            "need_clarity": 15,
            "timeline_urgency": 15,
            "email_engagement": 15,
            "followup_responsiveness": 15,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=60.0,
            margin=0.35,
            segment="High Intent"
        )
        
        assert "High-intent" in explanation.strategic_fit

    def test_price_sensitive_segment_strategic_fit(self, service):
        """Test Price Sensitive segment strategic fit description."""
        breakdown = {
            "budget_signal": 10,
            "authority_level": 10,
            "need_clarity": 10,
            "timeline_urgency": 8,
            "email_engagement": 10,
            "followup_responsiveness": 15,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=45.0,
            margin=0.35,
            segment="Price Sensitive"
        )
        
        assert "Price-sensitive" in explanation.strategic_fit


class TestDetermineRecommendation:
    """Tests for _determine_recommendation method."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return OpportunityScoringService()

    def test_approve_high_probability_no_risks(self, service):
        """Test APPROVE for high probability without risks."""
        result = service._determine_recommendation(
            final_probability=80.0,
            risk_flags=[],
            positive_factors=["Budget", "Authority"]
        )
        assert result == "APPROVE"

    def test_review_with_risk_flags(self, service):
        """Test REVIEW when risk flags present."""
        result = service._determine_recommendation(
            final_probability=80.0,
            risk_flags=["Low margin"],
            positive_factors=["Budget", "Authority"]
        )
        assert result == "REVIEW"

    def test_review_medium_probability(self, service):
        """Test REVIEW for medium probability."""
        result = service._determine_recommendation(
            final_probability=60.0,
            risk_flags=[],
            positive_factors=["Budget"]
        )
        assert result == "REVIEW"

    def test_review_many_positive_factors(self, service):
        """Test REVIEW with many positive factors even with low probability."""
        result = service._determine_recommendation(
            final_probability=40.0,
            risk_flags=[],
            positive_factors=["Budget", "Authority", "Need", "Timeline"]
        )
        assert result == "REVIEW"

    def test_reject_low_probability(self, service):
        """Test REJECT for low probability with few positive factors."""
        result = service._determine_recommendation(
            final_probability=30.0,
            risk_flags=[],
            positive_factors=["Budget"]
        )
        assert result == "REJECT"


class TestDetermineStrategicFit:
    """Tests for _determine_strategic_fit method."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return OpportunityScoringService()

    def test_enterprise_high_value(self, service):
        """Test Enterprise segment with strong factors."""
        result = service._determine_strategic_fit(
            segment="Enterprise",
            positive_factors=["Budget", "Authority", "Need"],
            risk_flags=[]
        )
        assert "High-value enterprise" in result

    def test_enterprise_with_risks(self, service):
        """Test Enterprise segment with risk factors."""
        result = service._determine_strategic_fit(
            segment="Enterprise",
            positive_factors=["Budget"],
            risk_flags=["Low margin"]
        )
        assert "risk factors" in result

    def test_strategic_segment(self, service):
        """Test Strategic segment."""
        result = service._determine_strategic_fit(
            segment="Strategic",
            positive_factors=["Budget"],
            risk_flags=[]
        )
        assert "Strategic account" in result

    def test_price_sensitive_with_risks(self, service):
        """Test Price Sensitive segment with risks."""
        result = service._determine_strategic_fit(
            segment="Price Sensitive",
            positive_factors=[],
            risk_flags=["Low margin"]
        )
        assert "margin concerns" in result


class TestDealExplanationToDict:
    """Tests for deal_explanation_to_dict method."""

    def test_conversion(self):
        """Test conversion of DealExplanation to dict."""
        explanation = DealExplanation(
            probability=75.0,
            confidence="High",
            positive_factors=["Budget signals detected"],
            negative_factors=["Extended timeline"],
            risk_flags=[],
            strategic_fit="Strong SMB opportunity",
            recommendation="APPROVE"
        )
        
        result = OpportunityScoringService.deal_explanation_to_dict(explanation)
        
        assert isinstance(result, dict)
        assert result["probability"] == 75.0
        assert result["confidence"] == "High"
        assert result["positive_factors"] == ["Budget signals detected"]
        assert result["negative_factors"] == ["Extended timeline"]
        assert result["risk_flags"] == []
        assert result["strategic_fit"] == "Strong SMB opportunity"
        assert result["recommendation"] == "APPROVE"


class TestConfidenceLevels:
    """Tests for confidence level determination."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return OpportunityScoringService()

    def test_high_confidence(self, service):
        """Test High confidence for probability >= 75."""
        breakdown = {
            "budget_signal": 20,
            "authority_level": 20,
            "need_clarity": 20,
            "timeline_urgency": 20,
            "email_engagement": 20,
            "followup_responsiveness": 20,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=75.0,
            margin=0.35,
            segment="SMB"
        )
        
        assert explanation.confidence == "High"

    def test_medium_confidence(self, service):
        """Test Medium confidence for 50 <= probability < 75."""
        breakdown = {
            "budget_signal": 15,
            "authority_level": 15,
            "need_clarity": 15,
            "timeline_urgency": 15,
            "email_engagement": 15,
            "followup_responsiveness": 15,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=60.0,
            margin=0.35,
            segment="SMB"
        )
        
        assert explanation.confidence == "Medium"

    def test_low_confidence(self, service):
        """Test Low confidence for probability < 50."""
        breakdown = {
            "budget_signal": 8,
            "authority_level": 10,
            "need_clarity": 10,
            "timeline_urgency": 8,
            "email_engagement": 8,
            "followup_responsiveness": 10,
        }
        
        explanation = service._generate_explanation(
            breakdown=breakdown,
            final_probability=40.0,
            margin=0.35,
            segment="SMB"
        )
        
        assert explanation.confidence == "Low"


class TestBantScoreHelpers:
    """Tests for BANT factor extraction and scoring helpers."""

    def test_extract_bant_factors_from_legacy_breakdown(self):
        breakdown = {
            "budget_signal": 20,
            "authority_level": 10,
            "need_clarity": 20,
            "timeline_urgency": 8,
            "email_engagement": 12,
        }

        result = OpportunityScoringService.extract_bant_factors(breakdown)
        assert result == {
            "budget_signal": 20,
            "authority_level": 10,
            "need_clarity": 20,
            "timeline_urgency": 8,
        }

    def test_extract_bant_factors_from_structured_breakdown(self):
        breakdown = {
            "positive_factors": ["Budget signals detected"],
            "factor_scores": {
                "budget_signal": 20,
                "authority_level": 20,
                "need_clarity": 10,
                "timeline_urgency": 8,
                "email_engagement": 16,
            },
        }

        result = OpportunityScoringService.extract_bant_factors(breakdown)
        assert result == {
            "budget_signal": 20,
            "authority_level": 20,
            "need_clarity": 10,
            "timeline_urgency": 8,
        }

    def test_calculate_bant_score(self):
        breakdown = {
            "budget_signal": 20,
            "authority_level": 20,
            "need_clarity": 10,
            "timeline_urgency": 10,
        }

        # (20 + 20 + 10 + 10) / 80 * 100 = 75
        assert OpportunityScoringService.calculate_bant_score(breakdown) == 75
