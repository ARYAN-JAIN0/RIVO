"""Sales agent: builds and advances deal intelligence with deterministic+LLM scoring and proposal generation."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.enums import LeadStatus
from app.database.db import get_db_session
from app.database.models import Lead
from app.services.rag_service import RAGService
from app.services.sales_intelligence_service import SalesIntelligenceService

logger = logging.getLogger(__name__)


def run_sales_agent() -> None:
    sis = SalesIntelligenceService()
    rag = RAGService()

    with get_db_session() as session:
        leads = session.query(Lead).filter(Lead.status == LeadStatus.CONTACTED.value).all()

    if not leads:
        logger.info("sales.no_contacted_leads", extra={"event": "sales.no_contacted_leads"})
        return

    logger.info("sales.phase3.start", extra={"event": "sales.phase3.start", "lead_count": len(leads)})

    for lead in leads:
        deal = sis.create_or_update_deal(lead, actor="sales_agent")

        contexts = rag.retrieve(
            tenant_id=lead.tenant_id,
            query=f"{lead.company} {lead.industry} objections pricing timeline",
            top_k=3,
        )
        if contexts:
            logger.info(
                "sales.rag.context_retrieved",
                extra={"event": "sales.rag.context_retrieved", "deal_id": deal.id, "context_count": len(contexts)},
            )

        # deterministic stage progression only via transition rules.
        if deal.stage == "Lead":
            sis.transition_stage(deal.id, "Qualified", actor="sales_agent", reason="Lead contacted and scored")
        if (deal.probability or 0) >= 70 and deal.stage == "Qualified":
            sis.transition_stage(deal.id, "Proposal Sent", actor="sales_agent", reason="Probability threshold met")
            sis.generate_proposal(deal.id)

        logger.info(
            "sales.deal.updated",
            extra={
                "event": "sales.deal.updated",
                "deal_id": deal.id,
                "lead_id": lead.id,
                "probability": deal.probability,
                "margin": deal.margin,
                "segment": deal.segment_tag,
            },
        )

    logger.info("sales.phase3.complete", extra={"event": "sales.phase3.complete"})


if __name__ == "__main__":
    run_sales_agent()
