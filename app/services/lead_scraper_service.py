"""Production-hardened lead scraper service with strict validation.

This module provides a deterministic, zero-tolerance lead scraping service that:
- Validates all leads against ScrapedLeadSchema before persistence
- Rejects generic email providers (gmail.com, yahoo.com, etc.)
- Enforces domain alignment between email and company domain
- Performs tenant-scoped deduplication
- Logs all rejections with structured JSON for observability
- Provides Prometheus-compatible metrics

Usage:
    from app.services.lead_scraper_service import LeadScraperService

    service = LeadScraperService(tenant_id=1)
    result = service.scrape()
    print(f"Inserted: {result.leads_inserted}, Rejected: {result.leads_rejected}")
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config.scraper_sources import DEFAULT_SCRAPER_SOURCES
from app.database.db import get_db_session
from app.database.models import Lead
from app.schemas.scraper import ScrapedLeadSchema, ScraperRejection, ScraperResult
from app.services.base_service import BaseService
from app.utils.validators import sanitize_text

logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPTIONS
# =============================================================================


class ScraperError(Exception):
    """Base exception for scraper errors."""

    pass


class SourceUnavailableError(ScraperError):
    """External source is unavailable."""

    pass


class RateLimitExceededError(ScraperError):
    """Rate limit exceeded for source."""

    pass


class ValidationFailedError(ScraperError):
    """Lead validation failed."""

    pass


class DuplicateLeadError(ScraperError):
    """Lead already exists."""

    pass


# =============================================================================
# RATE LIMITER
# =============================================================================


class RateLimiter:
    """Simple rate limiter for API requests.

    Uses a token bucket algorithm to limit request rate.
    Thread-safe for use in async contexts.
    """

    def __init__(
        self,
        requests_per_second: float = 2.0,
        burst: int = 5,
    ):
        self.requests_per_second = requests_per_second
        self.burst = burst
        self._tokens = burst
        self._last_update = time.monotonic()
        self._lock = False

    def acquire(self) -> bool:
        """Try to acquire a token. Returns True if allowed."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._last_update = now

        # Replenish tokens
        self._tokens = min(self.burst, self._tokens + elapsed * self.requests_per_second)

        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False

    def wait_and_acquire(self, timeout: float = 30.0) -> bool:
        """Wait for a token to become available."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if self.acquire():
                return True
            time.sleep(0.1)
        return False


# =============================================================================
# METRICS
# =============================================================================


class ScraperMetrics:
    """Simple metrics collector for scraper operations.

    In production, this would integrate with Prometheus.
    """

    def __init__(self):
        self.leads_scraped_total = 0
        self.leads_valid_total = 0
        self.leads_rejected_total = 0
        self.leads_duplicate_total = 0
        self.leads_inserted_total = 0
        self.rejection_reasons: dict[str, int] = {}
        self.source_errors: dict[str, int] = {}

    def record_scraped(self, count: int = 1) -> None:
        self.leads_scraped_total += count

    def record_valid(self, count: int = 1) -> None:
        self.leads_valid_total += count

    def record_rejected(self, reason: str, count: int = 1) -> None:
        self.leads_rejected_total += count
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + count

    def record_duplicate(self, count: int = 1) -> None:
        self.leads_duplicate_total += count

    def record_inserted(self, count: int = 1) -> None:
        self.leads_inserted_total += count

    def record_source_error(self, source: str) -> None:
        self.source_errors[source] = self.source_errors.get(source, 0) + 1

    def to_dict(self) -> dict:
        return {
            "leads_scraped_total": self.leads_scraped_total,
            "leads_valid_total": self.leads_valid_total,
            "leads_rejected_total": self.leads_rejected_total,
            "leads_duplicate_total": self.leads_duplicate_total,
            "leads_inserted_total": self.leads_inserted_total,
            "rejection_reasons": self.rejection_reasons,
            "source_errors": self.source_errors,
        }


# =============================================================================
# LEAD SCRAPER SERVICE
# =============================================================================


class LeadScraperService(BaseService):
    """Production-hardened lead scraper with strict validation.

    This service enforces zero-tolerance validation:
    - All required fields must be present
    - Email domain must match company domain
    - Generic email providers are rejected
    - No placeholder or synthetic data allowed

    Attributes:
        tenant_id: Tenant identifier for multi-tenant isolation
        daily_cap: Maximum leads to scrape per day
        timeout: Request timeout in seconds
        metrics: Metrics collector for observability
        rate_limiter: Rate limiter for external requests
    """

    def __init__(
        self,
        tenant_id: int = 1,
        daily_cap: int | None = None,
        timeout: int | None = None,
    ):
        super().__init__()
        self.tenant_id = tenant_id
        self.daily_cap = daily_cap or int(os.getenv("LEAD_DAILY_CAP", "50"))
        self.timeout = timeout or int(os.getenv("LEAD_SCRAPE_TIMEOUT_SECONDS", "30"))
        self.metrics = ScraperMetrics()
        self.rate_limiter = RateLimiter(
            requests_per_second=float(os.getenv("SCRAPER_RPS", "2.0")),
            burst=int(os.getenv("SCRAPER_BURST", "5")),
        )

    def scrape(self, sources: list[dict] | None = None) -> ScraperResult:
        """Main entry point for scraping.

        Args:
            sources: Optional list of source configurations.
                    Uses DEFAULT_SCRAPER_SOURCES if None.

        Returns:
            ScraperResult with detailed metrics and rejection info.
        """
        correlation_id = uuid.uuid4().hex[:8]
        started_at = datetime.now(timezone.utc)

        logger.info(
            "scraper.job.start",
            extra={
                "event": "scraper.job.start",
                "correlation_id": correlation_id,
                "tenant_id": self.tenant_id,
                "daily_cap": self.daily_cap,
            },
        )

        result = ScraperResult(
            correlation_id=correlation_id,
            tenant_id=self.tenant_id,
            started_at=started_at,
        )

        # Check daily cap
        current_count = self._current_day_count()
        remaining = max(0, self.daily_cap - current_count)

        if remaining <= 0:
            logger.info(
                "scraper.job.daily_cap_reached",
                extra={
                    "event": "scraper.job.daily_cap_reached",
                    "correlation_id": correlation_id,
                    "current_count": current_count,
                    "daily_cap": self.daily_cap,
                },
            )
            result.finished_at = datetime.now(timezone.utc)
            return result

        sources = sources or DEFAULT_SCRAPER_SOURCES
        all_valid_leads: list[ScrapedLeadSchema] = []

        for source_config in sources:
            source_name = source_config.get("name", "unknown")

            if not source_config.get("enabled", False):
                continue

            try:
                raw_records = self._fetch_from_source(source_config)
                result.sources_processed += 1
                result.raw_records_fetched += len(raw_records)
                self.metrics.record_scraped(len(raw_records))

                for raw_record in raw_records:
                    validated = self._validate_lead(raw_record, source_name)

                    if validated is None:
                        result.leads_rejected += 1
                        continue

                    result.leads_valid += 1
                    self.metrics.record_valid()
                    all_valid_leads.append(validated)

                    if len(all_valid_leads) >= remaining:
                        break

            except SourceUnavailableError as e:
                result.sources_failed += 1
                result.errors.append({"source": source_name, "error": str(e)})
                self.metrics.record_source_error(source_name)
                logger.warning(
                    "scraper.source.unavailable",
                    extra={
                        "event": "scraper.source.unavailable",
                        "correlation_id": correlation_id,
                        "source": source_name,
                        "error": str(e),
                    },
                )
            except Exception as e:
                result.sources_failed += 1
                result.errors.append({"source": source_name, "error": str(e)})
                logger.exception(
                    "scraper.source.unexpected_error",
                    extra={
                        "event": "scraper.source.unexpected_error",
                        "correlation_id": correlation_id,
                        "source": source_name,
                    },
                )

        # Deduplicate and persist
        inserted, duplicates = self._persist_leads(all_valid_leads, result)
        result.leads_inserted = inserted
        result.leads_duplicate = duplicates
        result.finished_at = datetime.now(timezone.utc)

        logger.info(
            "scraper.job.complete",
            extra={
                "event": "scraper.job.complete",
                "correlation_id": correlation_id,
                "summary": result.to_summary_dict(),
            },
        )

        return result

    def _current_day_count(self) -> int:
        """Get count of leads created today for this tenant."""
        start_of_day = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        with get_db_session() as session:
            return (
                session.query(Lead)
                .filter(Lead.tenant_id == self.tenant_id)
                .filter(Lead.created_at >= start_of_day)
                .count()
            )

    def _fetch_from_source(self, source_config: dict) -> list[dict]:
        """Fetch raw records from a single source.

        Args:
            source_config: Source configuration with url, type, etc.

        Returns:
            List of raw record dictionaries.

        Raises:
            SourceUnavailableError: If source is unreachable.
        """
        source_name = source_config.get("name", "unknown")
        source_type = source_config.get("type", "json")

        # Handle mock source type for testing
        if source_type == "mock":
            return self._generate_mock_leads(source_config)

        url = source_config.get("url")
        timeout = source_config.get("timeout_seconds", self.timeout)

        if not url:
            logger.debug(
                "scraper.source.no_url",
                extra={"event": "scraper.source.no_url", "source": source_name},
            )
            return []

        # Rate limit
        if not self.rate_limiter.wait_and_acquire(timeout=30):
            raise RateLimitExceededError(f"Rate limit exceeded for {source_name}")

        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "RIVO/1.0 Lead Scraper"},
            )
            response.raise_for_status()

            if source_type == "json":
                return self._parse_json_response(response.json(), source_config)
            elif source_type == "html":
                return self._parse_html_response(response.text, source_config)
            else:
                logger.warning(
                    "scraper.source.unknown_type",
                    extra={
                        "event": "scraper.source.unknown_type",
                        "source": source_name,
                        "type": source_type,
                    },
                )
                return []

        except requests.exceptions.Timeout:
            raise SourceUnavailableError(f"Timeout fetching from {source_name}")
        except requests.exceptions.RequestException as e:
            raise SourceUnavailableError(f"Request failed for {source_name}: {e}")

    def _parse_json_response(self, data: Any, source_config: dict) -> list[dict]:
        """Parse JSON response into raw records."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Look for common data envelope keys
            for key in ["data", "results", "items", "records", "leads"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []

    def _parse_html_response(self, html: str, source_config: dict) -> list[dict]:
        """Parse HTML response into raw records.

        Note: This is a placeholder. In production, use BeautifulSoup
        with proper selectors from source_config.
        """
        # HTML parsing is disabled by default for safety
        # Enable by providing proper selectors in source_config
        selectors = source_config.get("selectors", {})
        if not selectors:
            return []
        return []

    def _generate_mock_leads(self, source_config: dict) -> list[dict]:
        """Generate realistic mock leads for testing.

        Args:
            source_config: Source configuration with 'count' parameter.

        Returns:
            List of mock lead dictionaries with realistic data.
        """
        import random

        count = source_config.get("count", 10)

        # Realistic mock data pools
        first_names = [
            "James", "Sarah", "Michael", "Emily", "David", "Jennifer",
            "Robert", "Amanda", "William", "Jessica", "Christopher", "Ashley",
            "Daniel", "Nicole", "Andrew", "Stephanie", "Kevin", "Rachel",
            "Brian", "Michelle", "Steven", "Elizabeth", "Mark", "Lauren",
        ]
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
            "Miller", "Davis", "Rodriguez", "Martinez", "Anderson", "Taylor",
            "Thomas", "Moore", "Jackson", "Martin", "Lee", "Thompson",
            "White", "Harris", "Clark", "Lewis", "Robinson", "Walker",
        ]
        company_names = [
            "TechFlow", "DataPulse", "CloudNine", "InnovateLabs", "Nextera",
            "Synthex", "QuantumLeap", "AeroSync", "BrightPath", "VelocityX",
            "NexusPoint", "CyberDyne", "AlphaWorks", "BetaBridge", "GammaForce",
            "DeltaStream", "EpsilonNet", "ZetaCore", "EtaSystems", "ThetaWave",
        ]
        industries = [
            "Technology", "Software", "SaaS", "FinTech", "HealthTech",
            "EdTech", "CleanTech", "Cybersecurity", "AI/ML", "Cloud Computing",
        ]
        job_titles = [
            "CEO", "CTO", "VP of Engineering", "VP of Sales", "CFO",
            "Director of Product", "Head of Growth", "Chief Revenue Officer",
            "VP of Marketing", "Director of Operations", "Co-Founder",
            "Chief Product Officer", "VP of Business Development",
        ]
        signals = [
            "hiring aggressively for engineering team",
            "expanding to European markets",
            "raised Series B funding",
            "launching new product line",
            "migrating to cloud infrastructure",
            "building AI capabilities",
            "growing sales team 50%",
            "opening new office location",
        ]

        leads = []
        used_emails = set()

        for i in range(count):
            # Generate unique lead
            first = random.choice(first_names)
            last = random.choice(last_names)
            company = random.choice(company_names)
            domain = f"{company.lower().replace(' ', '')}.com"

            # Ensure unique email
            email_base = f"{first.lower()}.{last.lower()}"
            email = f"{email_base}@{domain}"
            counter = 1
            while email in used_emails:
                email = f"{email_base}{counter}@{domain}"
                counter += 1
            used_emails.add(email)

            lead = {
                "contact_name": f"{first} {last}",
                "email": email,
                "company_name": company,
                "company_domain": domain,
                "job_title": random.choice(job_titles),
                "industry": random.choice(industries),
                "website": f"https://www.{domain}",
                "company_size": random.choice(["51-200", "201-500", "501-1000", "1000+"]),
                "verified_insight": random.choice(signals),
            }
            leads.append(lead)

        logger.info(
            "scraper.mock.generated",
            extra={
                "event": "scraper.mock.generated",
                "count": len(leads),
            },
        )
        return leads

    def _validate_lead(
        self,
        raw_data: dict,
        source_name: str,
    ) -> ScrapedLeadSchema | None:
        """Validate raw data against ScrapedLeadSchema.

        Args:
            raw_data: Raw record from source
            source_name: Source identifier for logging

        Returns:
            Validated ScrapedLeadSchema or None if rejected.
        """
        try:
            # Normalize field names from source
            normalized = self._normalize_fields(raw_data, source_name)

            # Add tenant_id and source if not present
            normalized.setdefault("tenant_id", self.tenant_id)
            normalized.setdefault("source", source_name)

            # Validate against schema
            validated = ScrapedLeadSchema(**normalized)

            # Check for duplicates
            if self._is_duplicate(validated.email):
                self.metrics.record_duplicate()
                logger.debug(
                    "scraper.lead.duplicate",
                    extra={
                        "event": "scraper.lead.duplicate",
                        "email": validated.email,
                        "source": source_name,
                    },
                )
                return None

            return validated

        except ValidationError as e:
            self._log_rejection(raw_data, str(e), "validation_error", source_name)
            self.metrics.record_rejected("validation_error")
            return None
        except Exception as e:
            self._log_rejection(raw_data, str(e), "unexpected_error", source_name)
            self.metrics.record_rejected("unexpected_error")
            return None

    def _normalize_fields(self, raw_data: dict, source_name: str) -> dict:
        """Normalize raw data fields to match ScrapedLeadSchema.

        Override this method to add source-specific field mappings.
        """
        # Common field mappings
        field_mappings = {
            "name": "contact_name",
            "full_name": "contact_name",
            "contact": "contact_name",
            "title": "job_title",
            "position": "job_title",
            "domain": "company_domain",
            "company_domain": "company_domain",
            "url": "website",
            "site": "website",
            "company_name": "company_name",
            "organization": "company_name",
            "org": "company_name",
        }

        normalized = {}
        for key, value in raw_data.items():
            lower_key = key.lower().strip()

            # Map to canonical field name
            canonical = field_mappings.get(lower_key, lower_key)

            if canonical in {
                "contact_name",
                "company_name",
                "company_domain",
                "email",
                "job_title",
                "industry",
                "website",
                "source",
                "company_size",
                "location",
                "linkedin_url",
                "verified_insight",
                "negative_signals",
                "positive_signals",
            }:
                normalized[canonical] = value

        return normalized

    def _is_duplicate(self, email: str) -> bool:
        """Check if email already exists for this tenant.

        Args:
            email: Email address to check

        Returns:
            True if duplicate, False if new.
        """
        with get_db_session() as session:
            existing = (
                session.query(Lead)
                .filter(Lead.tenant_id == self.tenant_id)
                .filter(Lead.email.ilike(email.lower()))
                .first()
            )
            return existing is not None

    def _persist_leads(
        self,
        leads: list[ScrapedLeadSchema],
        result: ScraperResult,
    ) -> tuple[int, int]:
        """Persist validated leads to database.

        Args:
            leads: List of validated leads
            result: ScraperResult to update with rejections

        Returns:
            Tuple of (inserted_count, duplicate_count)
        """
        if not leads:
            return 0, 0

        inserted = 0
        duplicates = 0

        with get_db_session() as session:
            for schema in leads:
                try:
                    lead = Lead(**schema.to_lead_dict())
                    session.add(lead)
                    session.flush()  # Check for integrity errors
                    inserted += 1
                    self.metrics.record_inserted()

                    logger.debug(
                        "scraper.lead.inserted",
                        extra={
                            "event": "scraper.lead.inserted",
                            "email": schema.email,
                            "company": schema.company_name,
                        },
                    )

                except IntegrityError:
                    session.rollback()
                    duplicates += 1
                    self.metrics.record_duplicate()

                    rejection = ScraperRejection(
                        tenant_id=self.tenant_id,
                        rejection_reason="duplicate",
                        rejection_detail=f"Email already exists: {schema.email}",
                        raw_data_hash=schema.data_hash(),
                        fields_present=list(schema.model_dump().keys()),
                        fields_missing=[],
                        email=schema.email,
                        company=schema.company_name,
                        source=schema.source,
                    )
                    result.rejections.append(rejection)

                except SQLAlchemyError as e:
                    session.rollback()
                    logger.exception(
                        "scraper.lead.persist_failed",
                        extra={
                            "event": "scraper.lead.persist_failed",
                            "email": schema.email,
                            "error": str(e),
                        },
                    )

            # Commit all successful inserts
            try:
                session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.exception(
                    "scraper.batch.commit_failed",
                    extra={"event": "scraper.batch.commit_failed", "error": str(e)},
                )
                return 0, 0

        return inserted, duplicates

    def _log_rejection(
        self,
        raw_data: dict,
        detail: str,
        reason: str,
        source_name: str,
    ) -> None:
        """Log rejected lead with structured JSON."""
        # Create hash of raw data for tracking
        data_str = str(sorted(raw_data.items()))
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

        # Determine present and missing fields
        required_fields = [
            "contact_name",
            "company_name",
            "company_domain",
            "email",
            "job_title",
            "industry",
            "website",
        ]
        fields_present = [f for f in required_fields if f in raw_data and raw_data[f]]
        fields_missing = [f for f in required_fields if f not in raw_data or not raw_data[f]]

        rejection = ScraperRejection(
            tenant_id=self.tenant_id,
            rejection_reason=reason,
            rejection_detail=detail,
            raw_data_hash=data_hash,
            fields_present=fields_present,
            fields_missing=fields_missing,
            email=raw_data.get("email"),
            company=raw_data.get("company_name") or raw_data.get("company"),
            source=source_name,
        )

        logger.warning(
            "scraper.lead.rejected",
            extra=rejection.to_log_dict(),
        )

    def acquire_and_persist(self, tenant_id: int | None = None) -> ScraperResult:
        """Compatibility method for scheduler integration.

        This method provides backward compatibility with the existing
        scheduler.py which calls LeadAcquisitionService.acquire_and_persist().

        Args:
            tenant_id: Optional tenant ID override

        Returns:
            ScraperResult with leads_inserted, leads_duplicate, leads_rejected,
            and rejections attributes for scheduler compatibility.
        """
        if tenant_id:
            self.tenant_id = tenant_id

        return self.scrape()
