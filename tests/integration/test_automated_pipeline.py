"""Integration tests for the automated pipeline system.

Tests cover:
- End-to-end automated pipeline execution
- Restart safety and idempotency
- No duplicate invoices/contracts
- Status transitions correctness
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import LeadStatus
from app.database.models import AgentRun, Contract, Deal, Invoice, Lead, Tenant
from app.tasks.scheduler import automated_pipeline_run_task, get_scheduler_status


@pytest.fixture
def mock_enabled_config():
    """Mock enabled configuration for testing."""
    mock_cfg = MagicMock()
    mock_cfg.AUTO_PIPELINE_ENABLED = True
    mock_cfg.AUTO_PIPELINE_INTERVAL_HOURS = 6
    mock_cfg.AUTO_PIPELINE_TENANT_ID = 1
    return mock_cfg


@pytest.fixture
def setup_tenant(isolated_session_factory):
    """Set up a tenant for testing."""
    session = isolated_session_factory()
    tenant = Tenant(id=1, name="Test Tenant", is_active=True)
    session.add(tenant)
    session.commit()
    return tenant


class TestEndToEndAutomatedPipeline:
    """End-to-end tests for automated pipeline execution."""

    def test_full_pipeline_with_new_leads(self, isolated_session_factory, mock_enabled_config, setup_tenant):
        """Test full pipeline execution when new leads are acquired."""
        from app.tasks import scheduler

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        # Mock acquisition to return new leads
        mock_acquisition_result = {
            "created": 3,
            "skipped": 0,
            "daily_cap": 15,
            "skipped_duplicates": 0,
        }

        # Mock agent execution to succeed
        mock_agent_result = {
            "status": "success",
            "run_id": 123,
            "duration_ms": 100,
        }

        # Create a mock ScraperResult object
        from datetime import datetime, timezone
        from app.schemas.scraper import ScraperResult

        mock_scraper_result = ScraperResult(
            correlation_id="test-correlation-id",
            tenant_id=1,
            started_at=datetime.now(timezone.utc),
            leads_inserted=3,
            leads_duplicate=0,
            leads_rejected=0,
        )

        with patch("app.tasks.scheduler.get_config", return_value=mock_enabled_config):
            with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                with patch("app.tasks.scheduler.LeadScraperService") as MockService:
                    mock_service = MockService.return_value
                    mock_service.acquire_and_persist.return_value = mock_scraper_result

                    with patch("app.tasks.scheduler.execute_agent_task", return_value=mock_agent_result):
                        result = automated_pipeline_run_task()

        assert result["status"] == "success"
        assert result["acquisition"]["created"] == 3
        assert result["pipeline"]["status"] == "success"
        assert "run_id" in result

    def test_pipeline_creates_no_duplicates_on_restart(self, isolated_session_factory, mock_enabled_config, setup_tenant):
        """Test that restarting pipeline doesn't create duplicates."""
        from app.tasks import scheduler

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        # Create an existing lead
        session = isolated_session_factory()
        existing_lead = Lead(
            tenant_id=1,
            name="Existing Lead",
            email="existing@test.com",
            company="Test Co",
            status=LeadStatus.NEW.value,
            source="scraped",
        )
        session.add(existing_lead)
        session.commit()
        existing_lead_id = existing_lead.id

        # Mock acquisition to try to insert the same lead
        from datetime import datetime, timezone
        from app.schemas.scraper import ScraperResult

        mock_scraper_result = ScraperResult(
            correlation_id="test-correlation-id",
            tenant_id=1,
            started_at=datetime.now(timezone.utc),
            leads_inserted=0,
            leads_duplicate=1,
            leads_rejected=0,
        )

        with patch("app.tasks.scheduler.get_config", return_value=mock_enabled_config):
            with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                with patch("app.tasks.scheduler.LeadScraperService") as MockService:
                    mock_service = MockService.return_value
                    mock_service.acquire_and_persist.return_value = mock_scraper_result

                    result = automated_pipeline_run_task()

        # Verify no new leads created
        session = isolated_session_factory()
        lead_count = session.query(Lead).filter(Lead.email == "existing@test.com").count()
        assert lead_count == 1

        # Verify pipeline was skipped (no new leads)
        assert result["pipeline"]["status"] == "skipped"


class TestRestartSafety:
    """Tests for restart-safe behavior."""

    def test_no_duplicate_contracts(self, isolated_session_factory, mock_enabled_config, setup_tenant):
        """Test that contracts are not duplicated."""
        session = isolated_session_factory()

        # Create a lead and deal
        lead = Lead(
            tenant_id=1,
            name="Test Lead",
            email="test@example.com",
            company="Test Co",
            status=LeadStatus.CONTACTED.value,
        )
        session.add(lead)
        session.commit()

        deal = Deal(
            tenant_id=1,
            lead_id=lead.id,
            company="Test Co",
            stage="Qualified",
            status="Open",
        )
        session.add(deal)
        session.commit()

        # Create an existing contract
        contract = Contract(
            contract_code="CTR-001",
            deal_id=deal.id,
            lead_id=lead.id,
            status="Negotiating",
        )
        session.add(contract)
        session.commit()
        original_contract_id = contract.id

        # Verify unique constraint
        duplicate_contract = Contract(
            contract_code="CTR-002",
            deal_id=deal.id,  # Same deal_id
            lead_id=lead.id,
            status="Negotiating",
        )
        session.add(duplicate_contract)

        # This should fail due to unique constraint on deal_id
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            session.commit()

    def test_no_duplicate_invoices(self, isolated_session_factory, mock_enabled_config, setup_tenant):
        """Test that invoices are not duplicated."""
        session = isolated_session_factory()

        # Create lead, deal, and contract
        lead = Lead(
            tenant_id=1,
            name="Test Lead",
            email="invoice@example.com",
            company="Test Co",
            status=LeadStatus.CONTACTED.value,
        )
        session.add(lead)
        session.commit()

        deal = Deal(
            tenant_id=1,
            lead_id=lead.id,
            company="Test Co",
            stage="Proposal Sent",
            status="Open",
        )
        session.add(deal)
        session.commit()

        contract = Contract(
            contract_code="CTR-002",
            deal_id=deal.id,
            lead_id=lead.id,
            status="Signed",
        )
        session.add(contract)
        session.commit()

        # Create an existing invoice
        invoice = Invoice(
            invoice_code="INV-001",
            contract_id=contract.id,
            lead_id=lead.id,
            amount=10000,
            status="Sent",
        )
        session.add(invoice)
        session.commit()

        # Try to create duplicate invoice
        duplicate_invoice = Invoice(
            invoice_code="INV-002",
            contract_id=contract.id,  # Same contract_id
            lead_id=lead.id,
            amount=10000,
            status="Sent",
        )
        session.add(duplicate_invoice)

        # This should fail due to unique constraint on contract_id
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            session.commit()

    def test_pipeline_run_tracking_prevents_concurrent(self, isolated_session_factory, mock_enabled_config, setup_tenant):
        """Test that concurrent pipeline runs are prevented."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        # Create an active pipeline run
        session = isolated_session_factory()
        active_run = AgentRun(
            tenant_id=1,
            agent_name="automated_pipeline",
            task_id="running-task",
            status="running",
            triggered_by="scheduler",
        )
        session.add(active_run)
        session.commit()

        # Try to start another run
        with patch("app.tasks.scheduler.get_config", return_value=mock_enabled_config):
            with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                result = automated_pipeline_run_task()

        # Should be skipped due to concurrent run
        assert result["status"] == "skipped"
        assert "Active pipeline run already in progress" in result["reason"]


class TestStatusTransitions:
    """Tests for correct status transitions."""

    def test_lead_status_remains_new_after_acquisition(self, isolated_session_factory, setup_tenant):
        """Test that newly acquired leads have status 'New'."""
        from app.services.lead_acquisition_service import LeadAcquisitionService

        session = isolated_session_factory()

        # Create a mock lead
        mock_lead = MagicMock()
        mock_lead.name = "New Lead"
        mock_lead.email = "newlead@example.com"
        mock_lead.company = "New Co"
        mock_lead.website = "https://newco.com"
        mock_lead.industry = "Tech"
        mock_lead.location = "Remote"

        service = LeadAcquisitionService()

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        with patch.object(service, "scrape_public_leads", return_value=[mock_lead]):
            with patch("app.services.lead_acquisition_service.get_db_session", _get_db_session):
                result = service.acquire_and_persist(tenant_id=1)

        # Verify lead was created with New status
        session = isolated_session_factory()
        new_lead = session.query(Lead).filter(Lead.email == "newlead@example.com").first()
        assert new_lead is not None
        assert new_lead.status == LeadStatus.NEW.value

    def test_agent_run_record_created_for_pipeline(self, isolated_session_factory, mock_enabled_config, setup_tenant):
        """Test that AgentRun records are created for pipeline runs."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        mock_acquisition_result = {"created": 1, "skipped": 0, "daily_cap": 15, "skipped_duplicates": 0}
        mock_agent_result = {"status": "success", "run_id": 123, "duration_ms": 100}

        # Create a mock ScraperResult object
        from datetime import datetime, timezone
        from app.schemas.scraper import ScraperResult

        mock_scraper_result = ScraperResult(
            correlation_id="test-correlation-id",
            tenant_id=1,
            started_at=datetime.now(timezone.utc),
            leads_inserted=1,
            leads_duplicate=0,
            leads_rejected=0,
        )

        with patch("app.tasks.scheduler.get_config", return_value=mock_enabled_config):
            with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                with patch("app.tasks.scheduler.LeadScraperService") as MockService:
                    mock_service = MockService.return_value
                    mock_service.acquire_and_persist.return_value = mock_scraper_result

                    with patch("app.tasks.scheduler.execute_agent_task", return_value=mock_agent_result):
                        result = automated_pipeline_run_task()

        # Verify AgentRun record was created
        session = isolated_session_factory()
        pipeline_run = (
            session.query(AgentRun)
            .filter(AgentRun.agent_name == "automated_pipeline")
            .order_by(AgentRun.created_at.desc())
            .first()
        )

        assert pipeline_run is not None
        assert pipeline_run.status == "success"
        assert pipeline_run.triggered_by == "scheduler"


class TestIdempotency:
    """Tests for idempotent operations."""

    def test_duplicate_email_skipped_gracefully(self, isolated_session_factory, setup_tenant):
        """Test that duplicate emails are skipped without errors."""
        from app.services.lead_acquisition_service import LeadAcquisitionService

        session = isolated_session_factory()

        # Create existing lead
        existing = Lead(
            tenant_id=1,
            name="Existing",
            email="dup@example.com",
            company="Existing Co",
            status=LeadStatus.NEW.value,
        )
        session.add(existing)
        session.commit()

        # Try to insert duplicate
        mock_lead = MagicMock()
        mock_lead.name = "Duplicate"
        mock_lead.email = "dup@example.com"  # Same email
        mock_lead.company = "Different Co"
        mock_lead.website = "https://different.com"
        mock_lead.industry = "Tech"
        mock_lead.location = "Remote"

        service = LeadAcquisitionService()

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        with patch.object(service, "scrape_public_leads", return_value=[mock_lead]):
            with patch("app.services.lead_acquisition_service.get_db_session", _get_db_session):
                result = service.acquire_and_persist(tenant_id=1)

        # Should skip the duplicate
        assert result["created"] == 0
        assert result["skipped_duplicates"] >= 1

        # Verify only one lead exists
        session = isolated_session_factory()
        count = session.query(Lead).filter(Lead.email == "dup@example.com").count()
        assert count == 1

    def test_multiple_pipeline_runs_create_separate_records(self, isolated_session_factory, mock_enabled_config, setup_tenant):
        """Test that multiple pipeline runs create separate AgentRun records."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        mock_acquisition_result = {"created": 1, "skipped": 0, "daily_cap": 15, "skipped_duplicates": 0}
        mock_agent_result = {"status": "success", "run_id": 123, "duration_ms": 100}

        # Create a mock ScraperResult object
        from datetime import datetime, timezone
        from app.schemas.scraper import ScraperResult

        mock_scraper_result = ScraperResult(
            correlation_id="test-correlation-id",
            tenant_id=1,
            started_at=datetime.now(timezone.utc),
            leads_inserted=1,
            leads_duplicate=0,
            leads_rejected=0,
        )

        # Run pipeline twice
        for _ in range(2):
            # Clear any active runs first
            session = isolated_session_factory()
            session.query(AgentRun).filter(AgentRun.status.in_(["queued", "running"])).delete()
            session.commit()

            with patch("app.tasks.scheduler.get_config", return_value=mock_enabled_config):
                with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                    with patch("app.tasks.scheduler.LeadScraperService") as MockService:
                        mock_service = MockService.return_value
                        mock_service.acquire_and_persist.return_value = mock_scraper_result

                        with patch("app.tasks.scheduler.execute_agent_task", return_value=mock_agent_result):
                            automated_pipeline_run_task()

        # Verify two separate records exist
        session = isolated_session_factory()
        runs = session.query(AgentRun).filter(AgentRun.agent_name == "automated_pipeline").all()
        assert len(runs) == 2


class TestSchedulerStatusEndpoint:
    """Tests for the scheduler status endpoint."""

    def test_status_returns_correct_config(self, isolated_session_factory, mock_enabled_config):
        """Test that status endpoint returns correct configuration."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        with patch("app.tasks.scheduler.get_config", return_value=mock_enabled_config):
            with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                status = get_scheduler_status()

        assert status["enabled"] is True
        assert status["interval_hours"] == 6
        assert status["tenant_id"] == 1

    def test_status_includes_last_run_info(self, isolated_session_factory, mock_enabled_config):
        """Test that status includes information about the last run."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        # Create a past run
        session = isolated_session_factory()
        past_run = AgentRun(
            tenant_id=1,
            agent_name="automated_pipeline",
            task_id="past-run",
            status="success",
            triggered_by="scheduler",
        )
        session.add(past_run)
        session.commit()

        with patch("app.tasks.scheduler.get_config", return_value=mock_enabled_config):
            with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                status = get_scheduler_status()

        assert status["last_run"] is not None
        assert status["last_run"]["status"] == "success"
