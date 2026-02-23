"""Strict Pydantic V2 schema for scraped lead data validation.

This module provides zero-tolerance validation for lead data:
- All required fields must be present and non-empty
- Email domain must align with company domain
- Generic email providers (gmail.com, yahoo.com, etc.) are rejected
- No placeholder or synthetic data allowed

Usage:
    from app.schemas.scraper import ScrapedLeadSchema

    try:
        lead = ScrapedLeadSchema(
            company_name="Acme Corp",
            company_domain="acme.com",
            contact_name="John Doe",
            email="john@acme.com",
            job_title="CEO",
            industry="Technology",
            website="https://acme.com",
            source="ycombinator",
        )
    except ValidationError as e:
        # Handle validation failure - lead is rejected
        pass
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# Generic email providers to reject (corporate emails required)
GENERIC_EMAIL_DOMAINS = frozenset({
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "aol.com",
    "icloud.com",
    "mail.com",
    "protonmail.com",
    "proton.me",
    "yandex.com",
    "zoho.com",
    "gmx.com",
    "live.com",
    "msn.com",
    "inbox.com",
    "fastmail.com",
    "hushmail.com",
    "tutanota.com",
    "disroot.org",
    "cock.li",
    "pm.me",
})

# Whitelist for specific exceptions (e.g., solo founders using personal email)
# Add lowercase emails here to allow them despite generic domain
WHITELISTED_GENERIC_EMAILS: frozenset[str] = frozenset({
    # Add specific whitelisted emails here as needed
    # Example: "john@gmail.com"
})

# Email validation pattern (RFC 5322 simplified)
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Domain validation pattern
DOMAIN_PATTERN = re.compile(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# URL validation pattern
URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,}"
    r"(?::\d+)?"
    r"(?:/[^\s]*)?$",
    re.IGNORECASE,
)


class ScrapedLeadSchema(BaseModel):
    """Strict schema for scraped lead data with zero tolerance for incomplete fields.

    All required fields must be populated. Validation failures result in
    immediate rejection - no partial saves or default patching allowed.

    Attributes:
        tenant_id: Tenant identifier for multi-tenant isolation
        company_name: Legal or trading name of the company
        company_domain: Primary domain of the company (e.g., "acme.com")
        contact_name: Full name of the contact person
        email: Corporate email address (must match company domain)
        job_title: Job title of the contact
        industry: Industry sector classification
        website: Company website URL
        source: Source identifier where lead was scraped from
        scraped_at: Timestamp when lead was scraped
        negative_signals: List of negative signals detected (empty if none)
        positive_signals: List of positive signals detected (empty if none)
        company_size: Optional employee count range
        location: Optional geographic location
        linkedin_url: Optional LinkedIn profile URL
        verified_insight: Optional research notes about the company
    """

    # Required fields - all must be populated
    tenant_id: int = Field(default=1, ge=1, description="Tenant identifier")
    company_name: str = Field(..., min_length=2, max_length=255, description="Company name")
    company_domain: str = Field(..., min_length=3, max_length=255, description="Company domain")
    contact_name: str = Field(..., min_length=2, max_length=255, description="Contact name")
    email: str = Field(..., min_length=5, max_length=320, description="Corporate email")
    job_title: str = Field(..., min_length=2, max_length=255, description="Job title")
    industry: str = Field(..., min_length=2, max_length=120, description="Industry sector")
    website: str = Field(..., min_length=5, max_length=255, description="Company website")
    source: str = Field(..., min_length=2, max_length=100, description="Lead source")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Scrape timestamp")

    # Signal fields - explicit lists, empty if none
    negative_signals: list[str] = Field(default_factory=list, description="Negative signals")
    positive_signals: list[str] = Field(default_factory=list, description="Positive signals")

    # Optional fields
    company_size: Optional[str] = Field(None, max_length=50, description="Company size")
    location: Optional[str] = Field(None, max_length=120, description="Location")
    linkedin_url: Optional[str] = Field(None, max_length=500, description="LinkedIn URL")
    verified_insight: Optional[str] = Field(None, max_length=2000, description="Research notes")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Validate email format and normalize to lowercase."""
        v = v.lower().strip()
        if not EMAIL_PATTERN.match(v):
            raise ValueError(f"Invalid email format: {v}")
        return v

    @field_validator("company_domain")
    @classmethod
    def validate_domain_format(cls, v: str) -> str:
        """Validate domain format and normalize to lowercase."""
        v = v.lower().strip()
        # Remove protocol if present
        if v.startswith(("http://", "https://", "www.")):
            v = re.sub(r"^(https?://)?(www\.)?", "", v)
        if not DOMAIN_PATTERN.match(v):
            raise ValueError(f"Invalid domain format: {v}")
        return v

    @field_validator("website")
    @classmethod
    def normalize_website(cls, v: str) -> str:
        """Normalize website URL with protocol."""
        v = v.lower().strip()
        if not v.startswith(("http://", "https://")):
            v = f"https://{v}"
        return v

    @field_validator("company_name", "contact_name", "job_title", "industry", "source")
    @classmethod
    def strip_and_validate_non_empty(cls, v: str) -> str:
        """Strip whitespace and ensure non-empty for required string fields."""
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be empty or whitespace only")
        return v

    @field_validator("negative_signals", "positive_signals", mode="before")
    @classmethod
    def normalize_signals(cls, v: list[str] | str | None) -> list[str]:
        """Normalize signals to a list of strings."""
        if v is None:
            return []
        if isinstance(v, str):
            # Handle comma-separated string
            return [s.strip() for s in v.split(",") if s.strip()]
        return [str(s).strip() for s in v if str(s).strip()]

    @model_validator(mode="after")
    def validate_domain_alignment(self) -> "ScrapedLeadSchema":
        """Ensure email domain aligns with company domain.

        Rules:
        1. Reject generic email providers (gmail.com, yahoo.com, etc.)
        2. Allow whitelisted emails even if generic
        3. Email domain must match company domain (with subdomain tolerance)
        """
        email_domain = self.email.split("@")[1]

        # Check for generic email providers
        if email_domain in GENERIC_EMAIL_DOMAINS:
            if self.email.lower() not in WHITELISTED_GENERIC_EMAILS:
                raise ValueError(
                    f"Generic email provider rejected: '{email_domain}'. "
                    f"Corporate email address required for B2B outreach. "
                    f"Email: {self.email}"
                )

        # Check domain alignment
        company_root = self._extract_root_domain(self.company_domain)
        email_root = self._extract_root_domain(email_domain)

        if company_root != email_root:
            # Allow if email is a corporate subdomain (e.g., mail.acme.com for acme.com)
            if not email_domain.endswith(f".{self.company_domain}"):
                # Also check if company_domain is a subdomain of email_domain
                if not self.company_domain.endswith(f".{email_domain}"):
                    if self.email.lower() not in WHITELISTED_GENERIC_EMAILS:
                        raise ValueError(
                            f"Domain mismatch: email domain '{email_domain}' "
                            f"does not match company domain '{self.company_domain}'. "
                            f"Email: {self.email}"
                        )

        return self

    @staticmethod
    def _extract_root_domain(domain: str) -> str:
        """Extract root domain from a potentially subdomained domain.

        Examples:
            mail.acme.com -> acme.com
            acme.com -> acme.com
            www.acme.co.uk -> acme.co.uk
        """
        parts = domain.split(".")
        # Handle special TLDs like co.uk, com.au
        if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "gov", "edu", "ac"}:
            return ".".join(parts[-3:])
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return domain

    def to_lead_dict(self) -> dict:
        """Convert validated schema to Lead model kwargs.

        Maps schema fields to Lead model field names for database persistence.
        """
        return {
            "tenant_id": self.tenant_id,
            "name": self.contact_name,
            "email": self.email,
            "role": self.job_title,
            "company": self.company_name,
            "website": self.website,
            "location": self.location or "",
            "company_size": self.company_size or "",
            "industry": self.industry,
            "verified_insight": self.verified_insight or "",
            "negative_signals": ",".join(self.negative_signals) if self.negative_signals else "",
            "status": "New",
            "review_status": "New",
            "source": self.source,
        }

    def data_hash(self) -> str:
        """Generate a hash of the lead data for deduplication tracking."""
        data = f"{self.tenant_id}:{self.email.lower()}:{self.company_name.lower()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    class Config:
        extra = "forbid"  # Reject unknown fields
        str_strip_whitespace = True
        validate_assignment = True


class ScraperRejection(BaseModel):
    """Structured record for rejected leads.

    Captures all details about why a lead was rejected during validation
    for observability and debugging purposes.
    """

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tenant_id: int
    rejection_reason: str
    rejection_detail: str
    raw_data_hash: str
    fields_present: list[str]
    fields_missing: list[str]
    email: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = None

    def to_log_dict(self) -> dict:
        """Convert to dictionary for structured logging."""
        return {
            "event": "scraper.lead.rejected",
            "timestamp": self.timestamp.isoformat(),
            "tenant_id": self.tenant_id,
            "rejection_reason": self.rejection_reason,
            "rejection_detail": self.rejection_detail,
            "raw_data_hash": self.raw_data_hash,
            "fields_present": self.fields_present,
            "fields_missing": self.fields_missing,
            "email": self.email,
            "company": self.company,
            "source": self.source,
        }


class ScraperResult(BaseModel):
    """Result of a scraping operation with detailed metrics."""

    correlation_id: str
    tenant_id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    sources_processed: int = 0
    sources_failed: int = 0
    raw_records_fetched: int = 0
    leads_valid: int = 0
    leads_rejected: int = 0
    leads_duplicate: int = 0
    leads_inserted: int = 0
    rejections: list[ScraperRejection] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Calculate duration of the scraping operation."""
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0

    def to_summary_dict(self) -> dict:
        """Generate a summary dictionary for logging and API responses."""
        return {
            "correlation_id": self.correlation_id,
            "tenant_id": self.tenant_id,
            "duration_seconds": self.duration_seconds,
            "sources_processed": self.sources_processed,
            "sources_failed": self.sources_failed,
            "raw_records_fetched": self.raw_records_fetched,
            "leads_valid": self.leads_valid,
            "leads_rejected": self.leads_rejected,
            "leads_duplicate": self.leads_duplicate,
            "leads_inserted": self.leads_inserted,
            "rejection_reasons": list(set(r.rejection_reason for r in self.rejections)),
        }
