import sys
import random
from pathlib import Path
from datetime import datetime, timedelta
from faker import Faker

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.startup import bootstrap
from app.database.db import get_db_session
from app.database.models import Lead

fake = Faker()

INDUSTRIES = ['SaaS', 'Fintech', 'Healthcare', 'E-commerce', 'Manufacturing', 'Logistics', 'EdTech', 'Cybersecurity']
ROLES = ['CTO', 'VP of Engineering', 'CEO', 'Founder', 'Head of Product', 'Director of IT', 'CFO', 'Operations Manager']
SIZES = ['10-50', '50-100', '100-500', '500-1000', '1000+', 'Enterprise']
INSIGHTS = [
    "Looking to migrate legacy systems to cloud.",
    "Raised Series B funding recently, scaling engineering team.",
    "Complaining about current vendor on Twitter.",
    "Hiring aggressively for DevOps roles.",
    "Expanding into new markets in Europe.",
    "Seeking to reduce operational costs by 20%.",
    "Suffered a security breach recently, looking for better protection.",
    "New CTO just joined the company.",
    "Attending upcoming industry conference.",
    "Posted about need for better data analytics tools."
]
NEGATIVE_SIGNALS = [
    "Recent layoffs reported.",
    "Competitor signed last month.",
    "Hiring freeze announced.",
    "Bad Glassdoor reviews about management.",
    "", "", "", "", "", "" # Empty strings for clean leads
]

def seed_20_leads() -> None:
    bootstrap()
    try:
        with get_db_session() as db:
            print("Seeding 20 diverse leads...")
            leads = []
            for _ in range(20):
                name = fake.name()
                company = fake.company()
                email = fake.unique.company_email()
                role = random.choice(ROLES)
                industry = random.choice(INDUSTRIES)
                size = random.choice(SIZES)
                insight = random.choice(INSIGHTS)
                negative = random.choice(NEGATIVE_SIGNALS)

                lead = Lead(
                    name=name,
                    company=company,
                    email=email,
                    role=role,
                    industry=industry,
                    company_size=size,
                    verified_insight=insight,
                    negative_signals=negative,
                    status="New",
                    created_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
                )
                leads.append(lead)

            db.add_all(leads)
            db.commit()
            print(f"Successfully added {len(leads)} leads to the database.")
    except Exception as e:
        print(f"Error seeding data: {e}")


if __name__ == "__main__":
    seed_20_leads()
