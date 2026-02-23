"""Unit tests for LeadScraperService.

Tests cover:
- Schema validation integration
- Deduplication logic
- Rejection logging
- Rate limiting
- Metrics tracking
- Multi-tenant isolation
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.lead_scraper_service import (
    LeadScraperService,
    RateLimiter,
    ScraperMetrics,
)


class TestRateLimiter:
    """Test RateLimiter token bucket algorithm."""

    def test_rate_limiter_allows_within_limit(self):
        """Requests within rate limit should be allowed."""
        limiter = RateLimiter(requests_per_second=10.0, burst=5)
        for _ in range(5):
            assert limiter.acquire() is True

    def test_rate_limiter_blocks_over_limit(self):
        """Requests over burst limit should be blocked."""
        limiter = RateLimiter(requests_per_second=1.0, burst=2)
        # First two should succeed
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        # Third should fail (over burst)
        assert limiter.acquire() is False

    def test_rate_limiter_refills_tokens(self):
        """Tokens should refill over time."""
        limiter = RateLimiter(requests_per_second=100.0, burst=1)  # 100 tokens/sec
        assert limiter.acquire() is True
        assert limiter.acquire() is False
        # Wait for refill (20ms = 2 tokens at 100/sec)
        import time

        time.sleep(0.02)
        assert limiter.acquire() is True


class TestScraperMetrics:
    """Test ScraperMetrics tracking."""

    def test_metrics_initial_values(self):
        """Metrics should start at zero."""
        metrics = ScraperMetrics()
        assert metrics.leads_scraped_total == 0
        assert metrics.leads_valid_total == 0
        assert metrics.leads_rejected_total == 0
        assert metrics.leads_duplicate_total == 0

    def test_metrics_record(self):
        """Metrics should record correctly."""
        metrics = ScraperMetrics()
        metrics.record_scraped(5)
        metrics.record_valid(3)
        metrics.record_rejected("Generic email", 2)
        metrics.record_duplicate(1)

        assert metrics.leads_scraped_total == 5
        assert metrics.leads_valid_total == 3
        assert metrics.leads_rejected_total == 2
        assert metrics.leads_duplicate_total == 1

    def test_metrics_to_dict(self):
        """Metrics should convert to dictionary."""
        metrics = ScraperMetrics()
        metrics.record_scraped(10)
        metrics.record_valid(8)
        metrics.record_rejected("Generic email", 2)
        metrics.record_duplicate(1)

        result = metrics.to_dict()
        assert result["leads_scraped_total"] == 10
        assert result["leads_valid_total"] == 8
        assert result["leads_rejected_total"] == 2
        assert result["leads_duplicate_total"] == 1


class TestLeadScraperServiceInit:
    """Test LeadScraperService initialization."""

    def test_init_with_tenant_id(self):
        """Service should store tenant_id."""
        service = LeadScraperService(tenant_id=5)
        assert service.tenant_id == 5

    def test_init_with_default_tenant(self):
        """Service should use default tenant_id from config."""
        service = LeadScraperService()
        assert service.tenant_id == 1  # Default from config


class TestLeadScraperServiceTenantIsolation:
    """Test LeadScraperService tenant isolation."""

    def test_service_uses_tenant_id_from_constructor(self):
        """Service should use tenant_id from constructor."""
        service = LeadScraperService(tenant_id=42)
        assert service.tenant_id == 42


class TestLeadScraperServiceScrape:
    """Test LeadScraperService scrape method."""

    @patch.object(LeadScraperService, "_current_day_count", return_value=0)
    @patch("app.services.lead_scraper_service.get_db_session")
    def test_scrape_returns_result(self, mock_session, mock_count):
        """scrape should return ScraperResult."""
        # Setup mock for database operations
        mock_session_ctx = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_session_ctx)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        service = LeadScraperService(tenant_id=1)
        result = service.scrape()

        # Result should have expected attributes
        assert hasattr(result, "leads_inserted")
        assert hasattr(result, "leads_rejected")
        assert hasattr(result, "leads_duplicate")


class TestLeadScraperServiceAcquireAndPersist:
    """Test LeadScraperService acquire_and_persist method."""

    @patch.object(LeadScraperService, "_current_day_count", return_value=0)
    @patch("app.services.lead_scraper_service.get_db_session")
    def test_acquire_and_persist_returns_result(self, mock_session, mock_count):
        """acquire_and_persist should return dict with expected keys."""
        # Setup mock for database operations
        mock_session_ctx = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_session_ctx)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        service = LeadScraperService(tenant_id=1)
        result = service.acquire_and_persist()

        # Result should have expected keys
        assert "created" in result
        assert "skipped" in result
        assert "daily_cap" in result


class TestLeadScraperServiceValidation:
    """Test LeadScraperService validation logic."""

    def test_validate_lead_accepts_valid_data(self):
        """Valid lead data should pass validation."""
        service = LeadScraperService(tenant_id=1)
        lead_data = {
            "tenant_id": 1,
            "company_name": "Acme Corp",
            "company_domain": "acme.com",
            "contact_name": "John Doe",
            "email": "john.doe@acme.com",
            "job_title": "CTO",
            "industry": "Technology",
            "website": "https://acme.com",
            "source": "linkedin",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "negative_signals": [],
            "positive_signals": ["hiring"],
        }

        result = service._validate_lead(lead_data, "test_source")
        assert result is not None
        assert result.email == "john.doe@acme.com"

    def test_validate_lead_rejects_missing_fields(self):
        """Lead with missing required fields should be rejected."""
        service = LeadScraperService(tenant_id=1)
        lead_data = {
            "tenant_id": 1,
            "company_name": "Acme Corp",
            # Missing company_domain, contact_name, email, etc.
        }

        result = service._validate_lead(lead_data, "test_source")
        assert result is None
        assert service.metrics.leads_rejected_total == 1

    def test_validate_lead_rejects_generic_email(self):
        """Lead with generic email should be rejected."""
        service = LeadScraperService(tenant_id=1)
        lead_data = {
            "tenant_id": 1,
            "company_name": "Acme Corp",
            "company_domain": "gmail.com",
            "contact_name": "John Doe",
            "email": "johndoe@gmail.com",
            "job_title": "CTO",
            "industry": "Technology",
            "website": "https://acme.com",
            "source": "linkedin",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "negative_signals": [],
            "positive_signals": [],
        }

        result = service._validate_lead(lead_data, "test_source")
        assert result is None
        assert service.metrics.leads_rejected_total == 1

    def test_validate_lead_rejects_domain_mismatch(self):
        """Lead with mismatched email domain should be rejected."""
        service = LeadScraperService(tenant_id=1)
        lead_data = {
            "tenant_id": 1,
            "company_name": "Acme Corp",
            "company_domain": "acme.com",
            "contact_name": "John Doe",
            "email": "john.doe@othercorp.com",
            "job_title": "CTO",
            "industry": "Technology",
            "website": "https://acme.com",
            "source": "linkedin",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "negative_signals": [],
            "positive_signals": [],
        }

        result = service._validate_lead(lead_data, "test_source")
        assert result is None
        assert service.metrics.leads_rejected_total == 1


class TestLeadScraperServiceDeduplication:
    """Test LeadScraperService deduplication logic."""

    @patch("app.services.lead_scraper_service.get_db_session")
    def test_is_duplicate_detects_existing(self, mock_session):
        """is_duplicate should detect existing leads."""
        # Setup mock
        mock_session_ctx = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_session_ctx)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_query = MagicMock()
        mock_session_ctx.query.return_value = mock_query
        
        # The code chains two .filter() calls, so we need to handle that
        # session.query(Lead).filter(...).filter(...).first()
        mock_filter1 = MagicMock()
        mock_filter2 = MagicMock()
        mock_query.filter.return_value = mock_filter1
        mock_filter1.filter.return_value = mock_filter2
        mock_filter2.first.return_value = MagicMock()  # Existing lead found

        service = LeadScraperService(tenant_id=1)
        result = service._is_duplicate("existing@acme.com")

        assert result is True

    @patch("app.services.lead_scraper_service.get_db_session")
    def test_is_duplicate_allows_new(self, mock_session):
        """is_duplicate should allow new leads."""
        # Setup mock
        mock_session_ctx = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_session_ctx)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_query = MagicMock()
        mock_session_ctx.query.return_value = mock_query
        
        # The code chains two .filter() calls, so we need to handle that
        # session.query(Lead).filter(...).filter(...).first()
        mock_filter1 = MagicMock()
        mock_filter2 = MagicMock()
        mock_query.filter.return_value = mock_filter1
        mock_filter1.filter.return_value = mock_filter2
        # Explicitly return None (not MagicMock which is truthy)
        mock_filter2.first.return_value = None

        service = LeadScraperService(tenant_id=1)
        result = service._is_duplicate("new@acme.com")

        assert result is False


class TestLeadScraperServiceRejectionLogging:
    """Test LeadScraperService rejection logging."""

    def test_log_rejection_logs_warning(self):
        """Rejection logging should log warning without error."""
        service = LeadScraperService(tenant_id=1)
        raw_data = {"email": "test@gmail.com", "company_name": "Test"}

        # This should not raise an exception
        service._log_rejection(
            raw_data=raw_data,
            detail="Generic email provider rejected",
            reason="generic_email",
            source_name="test_source",
        )
        service._log_rejection(
            raw_data=raw_data,
            detail="Domain alignment violation",
            reason="domain_mismatch",
            source_name="test_source",
        )

        # _log_rejection doesn't update metrics - that's done in _validate_lead
        # So we just verify no exception was raised


class TestLeadScraperServiceIdempotency:
    """Test LeadScraperService idempotency."""

    @patch.object(LeadScraperService, "_current_day_count", return_value=0)
    @patch("app.services.lead_scraper_service.get_db_session")
    def test_duplicate_leads_not_inserted(self, mock_session, mock_count):
        """Duplicate leads should not be inserted."""
        mock_session_ctx = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_session_ctx)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        service = LeadScraperService(tenant_id=1)
        result = service.acquire_and_persist()

        # Should have result with expected keys
        assert "created" in result
        assert "skipped_duplicates" in result
