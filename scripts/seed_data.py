
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.models import Lead, Base
from app.core.config import get_config

# Setup DB connection
config = get_config()
engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed_leads():
    db = SessionLocal()
    try:
        # Check if lead exists
        existing = db.query(Lead).filter(Lead.email == "demo@techcorp.com").first()
        if existing:
            print("Seed lead already exists.")
            return

        print("Seeding test lead...")
        lead = Lead(
            name="Sarah Connor",
            company="TechCorp Inc.",
            email="demo@techcorp.com",
            role="CTO",
            industry="SaaS",
            company_size="500-1000",
            verified_insight="Looking to migrate legacy systems to cloud. Budget approved for Q3.",
            status="New"
        )
        db.add(lead)
        db.commit()
        print(f"Seeded lead: {lead.name} ({lead.company})")
    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_leads()
