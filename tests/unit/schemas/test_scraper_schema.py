"""Unit tests for ScrapedLeadSchema validation.

Tests cover:
- Required field validation
- Domain alignment validation
- Generic email rejection
- Whitelisted generic emails
- Optional fields handling
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.scraper import (
    GENERIC_EMAIL_DOMAINS,
    ScrapedLeadSchema,
    ScraperRejection,
    ScraperResult,
    WHITELISTED_GENERIC_EMAILS,
)


class TestScrapedLeadSchemaRequiredFields:
    """Test required field validation."""

    def test_valid_lead_with_all_required_fields(self):
        """A lead with all required fields should validate successfully."""
        lead = ScrapedLeadSchema(
            tenant_id=1,
            company_name="Acme Corp",
            company_domain="acme.com",
            contact_name="John Doe",
            email="john.doe@acme.com",
            job_title="CTO",
            industry="Technology",
            website="https://acme.com",
            source="linkedin",
            scraped_at=datetime.now(timezone.utc),
            negative_signals=[],
            positive_signals=["hiring"],
        )
        assert lead.tenant_id == 1
        assert lead.company_name == "Acme Corp"
        assert lead.company_domain == "acme.com"
        assert lead.contact_name == "John Doe"
        assert lead.email == "john.doe@acme.com"
        assert lead.job_title == "CTO"
        assert lead.industry == "Technology"
        assert lead.website == "https://acme.com"
        assert lead.source == "linkedin"
        assert lead.negative_signals == []
        assert lead.positive_signals == ["hiring"]

    def test_missing_company_name_raises_validation_error(self):
        """Missing company_name should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ScrapedLeadSchema(
                tenant_id=1,
                company_domain="acme.com",
                contact_name="John Doe",
                email="john.doe@acme.com",
                job_title="CTO",
                industry="Technology",
                website="https://acme.com",
                source="linkedin",
                scraped_at=datetime.now(timezone.utc),
                negative_signals=[],
                positive_signals=[],
            )
        assert "company_name" in str(exc_info.value)

    def test_missing_email_raises_validation_error(self):
        """Missing email should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ScrapedLeadSchema(
                tenant_id=1,
                company_name="Acme Corp",
                company_domain="acme.com",
                contact_name="John Doe",
                job_title="CTO",
                industry="Technology",
                website="https://acme.com",
                source="linkedin",
                scraped_at=datetime.now(timezone.utc),
                negative_signals=[],
                positive_signals=[],
            )
        assert "email" in str(exc_info.value)


class TestScrapedLeadSchemaDomainAlignment:
    """Test domain alignment validation."""

    def test_matching_domain_validates(self):
        """Email domain matching company domain should validate."""
        lead = ScrapedLeadSchema(
            tenant_id=1,
            company_name="Acme Corp",
            company_domain="acme.com",
            contact_name="John Doe",
            email="john.doe@acme.com",
            job_title="CTO",
            industry="Technology",
            website="https://acme.com",
            source="linkedin",
            scraped_at=datetime.now(timezone.utc),
            negative_signals=[],
            positive_signals=[],
        )
        assert lead.email == "john.doe@acme.com"

    def test_subdomain_matches_parent_domain(self):
        """Email from subdomain should match parent company domain."""
        lead = ScrapedLeadSchema(
            tenant_id=1,
            company_name="Acme Corp",
            company_domain="acme.com",
            contact_name="John Doe",
            email="john.doe@sub.acme.com",
            job_title="CTO",
            industry="Technology",
            website="https://acme.com",
            source="linkedin",
            scraped_at=datetime.now(timezone.utc),
            negative_signals=[],
            positive_signals=[],
        )
        assert lead.email == "john.doe@sub.acme.com"

    def test_company_subdomain_matches_email_domain(self):
        """Email domain should match company subdomain."""
        lead = ScrapedLeadSchema(
            tenant_id=1,
            company_name="Acme Corp",
            company_domain="sub.acme.com",
            contact_name="John Doe",
            email="john.doe@sub.acme.com",
            job_title="CTO",
            industry="Technology",
            website="https://sub.acme.com",
            source="linkedin",
            scraped_at=datetime.now(timezone.utc),
            negative_signals=[],
            positive_signals=[],
        )
        assert lead.email == "john.doe@sub.acme.com"

    def test_mismatched_domain_raises_validation_error(self):
        """Email domain not matching company domain should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ScrapedLeadSchema(
                tenant_id=1,
                company_name="Acme Corp",
                company_domain="acme.com",
                contact_name="John Doe",
                email="john.doe@othercorp.com",
                job_title="CTO",
                industry="Technology",
                website="https://acme.com",
                source="linkedin",
                scraped_at=datetime.now(timezone.utc),
                negative_signals=[],
                positive_signals=[],
            )
        # Check for domain mismatch message
        assert "Domain mismatch" in str(exc_info.value)


class TestScrapedLeadSchemaGenericEmail:
    """Test generic email provider rejection."""

    def test_gmail_email_rejected(self):
        """Gmail email should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ScrapedLeadSchema(
                tenant_id=1,
                company_name="Acme Corp",
                company_domain="gmail.com",
                contact_name="John Doe",
                email="johndoe@gmail.com",
                job_title="CTO",
                industry="Technology",
                website="https://acme.com",
                source="linkedin",
                scraped_at=datetime.now(timezone.utc),
                negative_signals=[],
                positive_signals=[],
            )
        assert "Generic email provider rejected" in str(exc_info.value)

    def test_yahoo_email_rejected(self):
        """Yahoo email should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ScrapedLeadSchema(
                tenant_id=1,
                company_name="Acme Corp",
                company_domain="yahoo.com",
                contact_name="John Doe",
                email="johndoe@yahoo.com",
                job_title="CTO",
                industry="Technology",
                website="https://acme.com",
                source="linkedin",
                scraped_at=datetime.now(timezone.utc),
                negative_signals=[],
                positive_signals=[],
            )
        assert "Generic email provider rejected" in str(exc_info.value)

    def test_hotmail_email_rejected(self):
        """Hotmail email should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ScrapedLeadSchema(
                tenant_id=1,
                company_name="Acme Corp",
                company_domain="hotmail.com",
                contact_name="John Doe",
                email="johndoe@hotmail.com",
                job_title="CTO",
                industry="Technology",
                website="https://acme.com",
                source="linkedin",
                scraped_at=datetime.now(timezone.utc),
                negative_signals=[],
                positive_signals=[],
            )
        assert "Generic email provider rejected" in str(exc_info.value)


class TestScrapedLeadSchemaOptionalFields:
    """Test optional field handling."""

    def test_optional_fields_can_be_omitted(self):
        """Optional fields can be omitted without error."""
        lead = ScrapedLeadSchema(
            tenant_id=1,
            company_name="Acme Corp",
            company_domain="acme.com",
            contact_name="John Doe",
            email="john.doe@acme.com",
            job_title="CTO",
            industry="Technology",
            website="https://acme.com",
            source="linkedin",
            scraped_at=datetime.now(timezone.utc),
            negative_signals=[],
            positive_signals=[],
        )
        assert lead.company_size is None
        assert lead.location is None
        assert lead.linkedin_url is None

    def test_optional_fields_can_be_provided(self):
        """Optional fields can be provided."""
        lead = ScrapedLeadSchema(
            tenant_id=1,
            company_name="Acme Corp",
            company_domain="acme.com",
            contact_name="John Doe",
            email="john.doe@acme.com",
            job_title="CTO",
            industry="Technology",
            website="https://acme.com",
            source="linkedin",
            scraped_at=datetime.now(timezone.utc),
            negative_signals=[],
            positive_signals=[],
            company_size="500-1000",
            location="San Francisco, CA",
            linkedin_url="https://linkedin.com/in/johndoe",
        )
        assert lead.company_size == "500-1000"
        assert lead.location == "San Francisco, CA"
        assert lead.linkedin_url == "https://linkedin.com/in/johndoe"


class TestScrapedLeadSchemaSignals:
    """Test negative_signals and positive_signals handling."""

    def test_empty_signals_lists(self):
        """Empty signals lists should be valid."""
        lead = ScrapedLeadSchema(
            tenant_id=1,
            company_name="Acme Corp",
            company_domain="acme.com",
            contact_name="John Doe",
            email="john.doe@acme.com",
            job_title="CTO",
            industry="Technology",
            website="https://acme.com",
            source="linkedin",
            scraped_at=datetime.now(timezone.utc),
            negative_signals=[],
            positive_signals=[],
        )
        assert lead.negative_signals == []
        assert lead.positive_signals == []

    def test_signals_with_values(self):
        """Signals with values should be stored correctly."""
        lead = ScrapedLeadSchema(
            tenant_id=1,
            company_name="Acme Corp",
            company_domain="acme.com",
            contact_name="John Doe",
            email="john.doe@acme.com",
            job_title="CTO",
            industry="Technology",
            website="https://acme.com",
            source="linkedin",
            scraped_at=datetime.now(timezone.utc),
            negative_signals=["layoff", "competitor"],
            positive_signals=["hiring", "expanding"],
        )
        assert lead.negative_signals == ["layoff", "competitor"]
        assert lead.positive_signals == ["hiring", "expanding"]


class TestScraperRejection:
    """Test ScraperRejection model."""

    def test_scraper_rejection_creation(self):
        """ScraperRejection should be created with required fields."""
        rejection = ScraperRejection(
            tenant_id=1,
            rejection_reason="Generic email provider rejected",
            rejection_detail="Email domain gmail.com is a generic provider",
            raw_data_hash="abc123",
            fields_present=["email", "company_name"],
            fields_missing=["company_domain"],
        )
        assert rejection.tenant_id == 1
        assert rejection.rejection_reason == "Generic email provider rejected"
        assert rejection.rejection_detail == "Email domain gmail.com is a generic provider"
        assert rejection.raw_data_hash == "abc123"
        assert rejection.fields_present == ["email", "company_name"]
        assert rejection.fields_missing == ["company_domain"]


class TestScraperResult:
    """Test ScraperResult model."""

    def test_scraper_result_creation(self):
        """ScraperResult should track all counts correctly."""
        result = ScraperResult(
            correlation_id="test-123",
            tenant_id=1,
            started_at=datetime.now(timezone.utc),
            leads_valid=10,
            leads_rejected=3,
            leads_duplicate=2,
            leads_inserted=10,
        )
        assert result.correlation_id == "test-123"
        assert result.tenant_id == 1
        assert result.leads_valid == 10
        assert result.leads_rejected == 3
        assert result.leads_duplicate == 2
        assert result.leads_inserted == 10

    def test_scraper_result_empty(self):
        """ScraperResult should handle empty results."""
        result = ScraperResult(
            correlation_id="test-456",
            tenant_id=1,
            started_at=datetime.now(timezone.utc),
        )
        assert result.correlation_id == "test-456"
        assert result.leads_valid == 0
        assert result.leads_rejected == 0
        assert result.leads_duplicate == 0
        assert result.leads_inserted == 0
        assert result.rejections == []


class TestGenericEmailDomains:
    """Test GENERIC_EMAIL_DOMAINS constant."""

    def test_gmail_in_generic_domains(self):
        """Gmail should be in generic domains."""
        assert "gmail.com" in GENERIC_EMAIL_DOMAINS

    def test_yahoo_in_generic_domains(self):
        """Yahoo should be in generic domains."""
        assert "yahoo.com" in GENERIC_EMAIL_DOMAINS

    def test_hotmail_in_generic_domains(self):
        """Hotmail should be in generic domains."""
        assert "hotmail.com" in GENERIC_EMAIL_DOMAINS

    def test_outlook_in_generic_domains(self):
        """Outlook should be in generic domains."""
        assert "outlook.com" in GENERIC_EMAIL_DOMAINS

    def test_corporate_domain_not_in_generic(self):
        """Corporate domains should not be in generic domains."""
        assert "acme.com" not in GENERIC_EMAIL_DOMAINS
        assert "google.com" not in GENERIC_EMAIL_DOMAINS


class TestScrapedLeadSchemaMethods:
    """Test ScrapedLeadSchema utility methods."""

    def test_to_lead_dict(self):
        """to_lead_dict should map schema fields to Lead model fields."""
        lead = ScrapedLeadSchema(
            tenant_id=1,
            company_name="Acme Corp",
            company_domain="acme.com",
            contact_name="John Doe",
            email="john.doe@acme.com",
            job_title="CTO",
            industry="Technology",
            website="https://acme.com",
            source="linkedin",
            scraped_at=datetime.now(timezone.utc),
            negative_signals=["layoff"],
            positive_signals=["hiring"],
        )
        lead_dict = lead.to_lead_dict()
        assert lead_dict["tenant_id"] == 1
        assert lead_dict["name"] == "John Doe"
        assert lead_dict["email"] == "john.doe@acme.com"
        assert lead_dict["role"] == "CTO"
        assert lead_dict["company"] == "Acme Corp"
        assert lead_dict["website"] == "https://acme.com"
        assert lead_dict["industry"] == "Technology"
        assert lead_dict["status"] == "New"
        assert lead_dict["source"] == "linkedin"

    def test_data_hash(self):
        """data_hash should generate consistent hash for same data."""
        lead1 = ScrapedLeadSchema(
            tenant_id=1,
            company_name="Acme Corp",
            company_domain="acme.com",
            contact_name="John Doe",
            email="john.doe@acme.com",
            job_title="CTO",
            industry="Technology",
            website="https://acme.com",
            source="linkedin",
            scraped_at=datetime.now(timezone.utc),
            negative_signals=[],
            positive_signals=[],
        )
        lead2 = ScrapedLeadSchema(
            tenant_id=1,
            company_name="Acme Corp",
            company_domain="acme.com",
            contact_name="John Doe",
            email="john.doe@acme.com",
            job_title="CTO",
            industry="Technology",
            website="https://acme.com",
            source="linkedin",
            scraped_at=datetime.now(timezone.utc),
            negative_signals=[],
            positive_signals=[],
        )
        assert lead1.data_hash() == lead2.data_hash()
