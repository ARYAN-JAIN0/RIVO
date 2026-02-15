import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.startup import bootstrap
from app.database.db import get_db_session
from app.database.models import Lead


def seed_leads() -> None:
    bootstrap()
    try:
        with get_db_session() as db:
            existing = db.query(Lead).filter(Lead.email == "demo@techcorp.com").first()
            if existing:
                existing.name = "Sarah Connor"
                existing.company = "TechCorp Inc."
                existing.role = "CTO"
                existing.industry = "SaaS"
                existing.company_size = "500-1000"
                existing.verified_insight = (
                    "Hiring rapidly and planning a stack migration with budget approved for Q4 immediate rollout."
                )
                existing.negative_signals = ""
                existing.status = "New"
                existing.review_status = "New"
                existing.draft_message = None
                existing.signal_score = None
                existing.confidence_score = None
                db.commit()
                print("Seed lead already existed; reset to high-signal New state.")
                return

            print("Seeding test lead...")
            lead = Lead(
                name="Sarah Connor",
                company="TechCorp Inc.",
                email="demo@techcorp.com",
                role="CTO",
                industry="SaaS",
                company_size="500-1000",
                verified_insight=(
                    "Hiring rapidly and planning a stack migration with budget approved for Q4 immediate rollout."
                ),
                negative_signals="",
                status="New",
            )
            db.add(lead)
            db.commit()
            print(f"Seeded lead: {lead.name} ({lead.company})")
    except Exception as e:
        print(f"Error seeding data: {e}")


if __name__ == "__main__":
    seed_leads()
