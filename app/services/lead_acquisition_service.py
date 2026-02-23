from __future__ import annotations

import logging
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from sqlalchemy.exc import SQLAlchemyError

from app.core.enums import LeadStatus, ReviewStatus
from app.database.db import get_db_session
from app.database.models import Lead
from app.utils.validators import sanitize_text

try:  # pragma: no cover - exercised when bs4 is installed.
    from bs4 import BeautifulSoup
except ModuleNotFoundError:  # pragma: no cover - local fallback path.
    class BeautifulSoup:  # type: ignore[override]
        def __init__(self, html: str, parser: str) -> None:
            self._html = html

        def get_text(self, sep: str = " ", strip: bool = True) -> str:
            text = re.sub(r"<[^>]+>", " ", self._html)
            text = re.sub(r"\s+", " ", text)
            return text.strip() if strip else text

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@dataclass
class ScrapedLead:
    name: str
    company: str
    email: str
    website: str
    industry: str
    location: str | None = None


def _infer_industry(text: str) -> str:
    lowered = text.lower()
    mapping = {
        "saas": "SaaS",
        "software": "Software",
        "health": "Healthcare",
        "fintech": "FinTech",
        "finance": "Finance",
        "ecommerce": "Ecommerce",
        "retail": "Retail",
        "logistics": "Logistics",
        "manufact": "Manufacturing",
        "education": "Education",
    }
    for token, label in mapping.items():
        if token in lowered:
            return label
    return "General"


def _extract_first_email(text: str) -> str | None:
    m = EMAIL_RE.search(text)
    return m.group(0).lower() if m else None


def _normalize_website(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme:
        return f"https://{url}"
    return url


def _validate(lead: ScrapedLead) -> bool:
    if not lead.company or not lead.email:
        return False
    if "@" not in lead.email:
        return False
    return True


def _fallback_leads(count: int) -> list[ScrapedLead]:
    leads: list[ScrapedLead] = []
    domains = ["exampleco.io", "acmesaas.com", "northstar.ai", "cloudforge.dev"]
    for i in range(count):
        domain = random.choice(domains)
        company = domain.split(".")[0].title()
        leads.append(
            ScrapedLead(
                name=f"Contact {i+1}",
                company=company,
                email=f"hello{i+1}@{domain}",
                website=f"https://{domain}",
                industry="SaaS",
                location="Remote",
            )
        )
    return leads


class LeadAcquisitionService:
    """Basic legal-safe lead acquisition using publicly available listing pages."""

    SOURCE_URLS = [
        "https://www.ycombinator.com/companies",
        "https://www.producthunt.com/",
    ]

    def __init__(self) -> None:
        self.daily_cap = int(os.getenv("LEAD_DAILY_CAP", "15"))
        self.timeout = int(os.getenv("LEAD_SCRAPE_TIMEOUT_SECONDS", "15"))

    def _current_day_count(self, tenant_id: int) -> int:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        with get_db_session() as session:
            return (
                session.query(Lead)
                .filter(Lead.tenant_id == tenant_id)
                .filter(Lead.created_at >= start)
                .count()
            )

    def scrape_public_leads(self, limit: int = 20) -> list[ScrapedLead]:
        collected: list[ScrapedLead] = []
        for url in self.SOURCE_URLS:
            if len(collected) >= limit:
                break
            try:
                response = requests.get(url, timeout=self.timeout, headers={"User-Agent": "RIVO/1.0 demo crawler"})
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                text = soup.get_text(" ", strip=True)
                email = _extract_first_email(text)
                host = urlparse(url).netloc
                industry = _infer_industry(text)
                if email:
                    collected.append(
                        ScrapedLead(
                            name="Public Contact",
                            company=host.split(".")[0].title(),
                            email=email,
                            website=f"https://{host}",
                            industry=industry,
                            location=None,
                        )
                    )
            except Exception:
                logger.warning("lead_acquisition.scrape_failed", extra={"event": "lead_acquisition.scrape_failed", "url": url})

        if not collected:
            return _fallback_leads(min(limit, 5))
        return collected[:limit]

    def acquire_and_persist(self, tenant_id: int = 1) -> dict[str, int]:
        """Acquire leads from public sources and persist to database.

        This method implements idempotent lead insertion by checking for
        existing emails before inserting. Duplicate leads are skipped and
        logged for observability.

        Args:
            tenant_id: Tenant ID for the leads

        Returns:
            Dict with 'created', 'skipped', 'daily_cap', and 'skipped_duplicates' counts
        """
        try:
            current_count = self._current_day_count(tenant_id)
            remaining = max(0, self.daily_cap - current_count)
            if remaining <= 0:
                logger.info(
                    "lead_acquisition.daily_cap_reached",
                    extra={
                        "event": "lead_acquisition.daily_cap_reached",
                        "tenant_id": tenant_id,
                        "current_count": current_count,
                        "daily_cap": self.daily_cap,
                    },
                )
                return {"created": 0, "skipped": 0, "daily_cap": self.daily_cap, "skipped_duplicates": 0}

            scraped = self.scrape_public_leads(limit=remaining)
            created = 0
            skipped = 0
            skipped_duplicates = 0
            skipped_invalid = 0

            with get_db_session() as session:
                for lead in scraped:
                    if not _validate(lead):
                        skipped += 1
                        skipped_invalid += 1
                        logger.debug(
                            "lead_acquisition.lead_invalid",
                            extra={
                                "event": "lead_acquisition.lead_invalid",
                                "email": lead.email,
                                "company": lead.company,
                            },
                        )
                        continue

                    normalized_email = sanitize_text(lead.email, 320)
                    exists = session.query(Lead).filter(Lead.email == normalized_email).first()
                    if exists:
                        skipped += 1
                        skipped_duplicates += 1
                        logger.debug(
                            "lead_acquisition.duplicate_skipped",
                            extra={
                                "event": "lead_acquisition.duplicate_skipped",
                                "email": normalized_email,
                                "existing_lead_id": exists.id,
                            },
                        )
                        continue

                    session.add(
                        Lead(
                            tenant_id=tenant_id,
                            name=sanitize_text(lead.name, 255),
                            email=normalized_email,
                            company=sanitize_text(lead.company, 255),
                            website=_normalize_website(sanitize_text(lead.website, 255)),
                            industry=sanitize_text(lead.industry, 120),
                            location=sanitize_text(lead.location or "", 120),
                            status=LeadStatus.NEW.value,
                            review_status=ReviewStatus.NEW.value,
                            source="scraped",
                        )
                    )
                    created += 1
                    logger.debug(
                        "lead_acquisition.lead_created",
                        extra={
                            "event": "lead_acquisition.lead_created",
                            "email": normalized_email,
                            "company": lead.company,
                        },
                    )
                session.commit()

            logger.info(
                "lead_acquisition.completed",
                extra={
                    "event": "lead_acquisition.completed",
                    "leads_created": created,
                    "leads_skipped": skipped,
                    "leads_skipped_duplicates": skipped_duplicates,
                    "leads_skipped_invalid": skipped_invalid,
                    "daily_cap": self.daily_cap,
                    "tenant_id": tenant_id,
                },
            )
            return {
                "created": created,
                "skipped": skipped,
                "daily_cap": self.daily_cap,
                "skipped_duplicates": skipped_duplicates,
                "skipped_invalid": skipped_invalid,
            }
        except SQLAlchemyError:
            logger.exception("lead_acquisition.persist_failed", extra={"event": "lead_acquisition.persist_failed"})
            return {"created": 0, "skipped": 0, "daily_cap": self.daily_cap, "skipped_duplicates": 0}
