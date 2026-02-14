from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.database.db import get_db_session
from app.database.models import Deal, DealStageAudit, EmailLog, Lead
from app.services.opportunity_scoring_service import OpportunityScoringService
from app.services.proposal_service import ProposalService
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

PIPELINE_STAGES = ["Lead", "Qualified", "Proposal Sent", "Negotiation", "Closed Won", "Closed Lost"]
ALLOWED_STAGE_TRANSITIONS = {
    "Lead": {"Qualified", "Closed Lost"},
    "Qualified": {"Proposal Sent", "Closed Lost"},
    "Proposal Sent": {"Negotiation", "Closed Won", "Closed Lost"},
    "Negotiation": {"Closed Won", "Closed Lost"},
    "Closed Won": set(),
    "Closed Lost": set(),
}


@dataclass
class MarginResult:
    margin: float
    low_margin_flag: bool


class SalesIntelligenceService:
    def __init__(self) -> None:
        self.scoring = OpportunityScoringService()
        self.proposal = ProposalService()
        self.rag = RAGService()

    @staticmethod
    def calculate_margin(deal_value: int, cost_estimate: int) -> MarginResult:
        if deal_value <= 0:
            return MarginResult(margin=0.0, low_margin_flag=True)
        margin = round((deal_value - cost_estimate) / deal_value, 4)
        return MarginResult(margin=margin, low_margin_flag=margin < 0.2)

    @staticmethod
    def segment_lead(lead: Lead, deal_value: int, engagement_count: int, close_days: int) -> str:
        industry = (lead.industry or "").lower()
        if deal_value >= 100000:
            return "Enterprise"
        if engagement_count >= 5 and close_days <= 30:
            return "High Intent"
        if any(k in industry for k in ["government", "public", "education"]):
            return "Strategic"
        if engagement_count <= 1 and (lead.followup_count or 0) >= 2:
            return "Price Sensitive"
        return "SMB"

    def _email_engagement_count(self, tenant_id: int, lead_id: int) -> int:
        with get_db_session() as session:
            return (
                session.query(EmailLog)
                .filter(EmailLog.tenant_id == tenant_id)
                .filter(EmailLog.lead_id == lead_id)
                .count()
            )

    def create_or_update_deal(self, lead: Lead, actor: str = "sales_agent") -> Deal:
        deal_value = 100000 if (lead.company_size or "").lower().find("enterprise") >= 0 else 25000
        engagement_count = self._email_engagement_count(lead.tenant_id, lead.id)
        close_days = 30 if engagement_count >= 3 else 60
        segment = self.segment_lead(lead, deal_value, engagement_count, close_days)

        score = self.scoring.score(lead, email_log_count=engagement_count)
        margin_result = self.calculate_margin(deal_value=deal_value, cost_estimate=int(deal_value * 0.65))

        with get_db_session() as session:
            deal = session.query(Deal).filter(Deal.lead_id == lead.id).first()
            if not deal:
                deal = Deal(
                    tenant_id=lead.tenant_id,
                    lead_id=lead.id,
                    company=lead.company,
                    stage="Lead",
                    status="Open",
                )
                session.add(deal)
                session.flush()

            deal.deal_value = deal_value
            deal.acv = deal_value
            deal.qualification_score = int(score.rule_score)
            deal.probability = score.final_probability
            deal.probability_confidence = score.confidence
            deal.probability_breakdown = score.breakdown
            deal.probability_explanation = score.explanation
            deal.expected_close_date = date.today() + timedelta(days=close_days)
            deal.cost_estimate = int(deal_value * 0.65)
            deal.margin = margin_result.margin
            deal.segment_tag = segment
            deal.forecast_month = deal.expected_close_date.strftime("%Y-%m")
            phase3_note = "[phase3] probability and margin refreshed"
            existing_notes = deal.notes or ""
            if phase3_note not in existing_notes:
                deal.notes = f"{existing_notes.rstrip()}\n{phase3_note}".strip()
            deal.last_updated = datetime.utcnow()

            session.commit()
            session.refresh(deal)

            self.rag.ingest_knowledge(
                tenant_id=lead.tenant_id,
                entity_type="deal",
                entity_id=deal.id,
                title=f"Deal summary: {lead.company}",
                content=score.explanation,
                source=actor,
            )
            return deal

    def transition_stage(self, deal_id: int, new_stage: str, actor: str = "system", reason: str = "") -> bool:
        if new_stage not in PIPELINE_STAGES:
            return False

        with get_db_session() as session:
            deal = session.query(Deal).filter(Deal.id == deal_id).first()
            if not deal:
                return False

            old_stage = deal.stage or "Lead"
            if new_stage not in ALLOWED_STAGE_TRANSITIONS.get(old_stage, set()):
                return False

            deal.stage = new_stage
            if new_stage in {"Closed Won", "Closed Lost"}:
                deal.status = "Closed"
            deal.last_updated = datetime.utcnow()
            session.add(
                DealStageAudit(
                    tenant_id=deal.tenant_id,
                    deal_id=deal.id,
                    old_stage=old_stage,
                    new_stage=new_stage,
                    actor=actor,
                    reason=reason,
                )
            )
            session.commit()
            return True

    def rescore_deal(self, deal_id: int, actor: str = "manual") -> bool:
        with get_db_session() as session:
            deal = session.query(Deal).filter(Deal.id == deal_id).first()
            if not deal:
                return False
            lead = session.query(Lead).filter(Lead.id == deal.lead_id).first()
            if not lead:
                return False

        self.create_or_update_deal(lead, actor=actor)
        return True

    def generate_proposal(self, deal_id: int) -> str | None:
        return self.proposal.generate_proposal(deal_id)
