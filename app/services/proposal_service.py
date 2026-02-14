from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from app.database.db import get_db_session
from app.database.models import Deal

logger = logging.getLogger(__name__)

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class ProposalService:
    def __init__(self) -> None:
        self.output_dir = Path("proposals")
        self.output_dir.mkdir(exist_ok=True)

    def generate_proposal(self, deal_id: int) -> str | None:
        if not REPORTLAB_AVAILABLE:
            logger.warning("proposal.reportlab.missing", extra={"event": "proposal.reportlab.missing"})
            return None

        with get_db_session() as session:
            deal = session.query(Deal).filter(Deal.id == deal_id).first()
            if not deal:
                return None

            next_version = int((deal.proposal_version or 0) + 1)
            filename = self.output_dir / f"proposal_deal_{deal_id}_v{next_version}.pdf"

            c = canvas.Canvas(str(filename), pagesize=letter)
            w, h = letter
            y = h - inch

            c.setFont("Helvetica-Bold", 18)
            c.drawString(inch, y, "RIVO Sales Proposal")
            y -= 0.4 * inch

            c.setFont("Helvetica", 11)
            lines = [
                f"Company: {deal.company or 'Unknown'}",
                f"Deal ID: {deal.id}",
                f"Deal Value: ${int(deal.deal_value or deal.acv or 0):,}",
                f"Stage: {deal.stage}",
                f"Expected Close: {(deal.expected_close_date or (datetime.utcnow().date() + timedelta(days=30))).isoformat()}",
                "",
                "Solution Overview:",
                "- Revenue lifecycle automation orchestration",
                "- Intelligent SDR/Sales/Negotiation/Finance handoff",
                "- Confidence-gated human oversight",
                "",
                "Pricing Breakdown:",
                "- Platform subscription",
                "- Onboarding & optimization",
                "",
                "Timeline:",
                "- Week 1: Discovery",
                "- Week 2-3: Integration",
                "- Week 4: Go-live",
                "",
                "Terms:",
                "- Net 30",
                "- Annual contract",
            ]
            for line in lines:
                c.drawString(inch, y, line)
                y -= 0.22 * inch
                if y < inch:
                    c.showPage()
                    y = h - inch

            c.save()

            deal.proposal_path = str(filename)
            deal.proposal_version = next_version
            session.commit()
            return str(filename)
