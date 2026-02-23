"""Unit tests for the automated pipeline scheduler.

Tests cover:
- Pipeline enabled/disabled configuration
- Duplicate lead prevention
- Concurrent run detection
- Sequential pipeline execution
- Error handling and failure propagation
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.database.models import AgentRun, Lead
from app.tasks.scheduler import (
    AGENT_ORDER,
    _check_active_pipeline_run,
    _create_pipeline_run_record,
    _get_tenant_id,
    _is_pipeline_enabled,
    _run_sequential_pipeline,
    _update_pipeline_run_status,
    automated_pipeline_run_task,
    get_scheduler_status,
)


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    mock_cfg = MagicMock()
    mock_cfg.AUTO_PIPELINE_ENABLED = True
    mock_cfg.AUTO_PIPELINE_INTERVAL_HOURS = 6
    mock_cfg.AUTO_PIPELINE_TENANT_ID = 1
    return mock_cfg


@pytest.fixture
def mock_disabled_config():
    """Mock disabled configuration for testing."""
    mock_cfg = MagicMock()
    mock_cfg.AUTO_PIPELINE_ENABLED = False
    mock_cfg.AUTO_PIPELINE_INTERVAL_HOURS = 6
    mock_cfg.AUTO_PIPELINE_TENANT_ID = 1
    return mock_cfg


class TestPipelineConfiguration:
    """Tests for pipeline configuration functions."""

    def test_is_pipeline_enabled_true(self, mock_config):
        """Test that pipeline is enabled when config is True."""
        with patch("app.tasks.scheduler.get_config", return_value=mock_config):
            assert _is_pipeline_enabled() is True

    def test_is_pipeline_enabled_false(self, mock_disabled_config):
        """Test that pipeline is disabled when config is False."""
        with patch("app.tasks.scheduler.get_config", return_value=mock_disabled_config):
            assert _is_pipeline_enabled() is False

    def test_get_tenant_id(self, mock_config):
        """Test getting tenant ID from config."""
        with patch("app.tasks.scheduler.get_config", return_value=mock_config):
            assert _get_tenant_id() == 1


class TestPipelineRunTracking:
    """Tests for pipeline run tracking in database."""

    def test_check_active_pipeline_run_no_active(self, isolated_session_factory):
        """Test that no active run is detected when none exists."""
        # The isolated_session_factory fixture patches db_handler.get_db_session
        # We need to also patch app.database.db.get_db_session
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        with patch("app.tasks.scheduler.get_db_session", _get_db_session):
            result = _check_active_pipeline_run(tenant_id=1)
            assert result is False

    def test_check_active_pipeline_run_with_active(self, isolated_session_factory):
        """Test that active run is detected when one exists."""
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
            task_id="test-task-123",
            status="running",
            triggered_by="scheduler",
        )
        session.add(active_run)
        session.commit()

        with patch("app.tasks.scheduler.get_db_session", _get_db_session):
            result = _check_active_pipeline_run(tenant_id=1)
            assert result is True

    def test_create_pipeline_run_record(self, isolated_session_factory):
        """Test creating a pipeline run record."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        with patch("app.tasks.scheduler.get_db_session", _get_db_session):
            run_id = _create_pipeline_run_record(tenant_id=1, task_id="test-task-456")
            assert run_id is not None
            assert isinstance(run_id, int)

    def test_update_pipeline_run_status(self, isolated_session_factory):
        """Test updating pipeline run status."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        # Create a run to update
        session = isolated_session_factory()
        run = AgentRun(
            tenant_id=1,
            agent_name="automated_pipeline",
            task_id="test-task-789",
            status="running",
            triggered_by="scheduler",
        )
        session.add(run)
        session.commit()
        run_id = run.id

        with patch("app.tasks.scheduler.get_db_session", _get_db_session):
            _update_pipeline_run_status(run_id, "success")

        # Verify update
        session = isolated_session_factory()
        updated_run = session.query(AgentRun).filter(AgentRun.id == run_id).first()
        assert updated_run.status == "success"
        assert updated_run.finished_at is not None


class TestSequentialPipeline:
    """Tests for sequential pipeline execution."""

    def test_run_sequential_pipeline_all_success(self, isolated_session_factory, mock_config):
        """Test successful sequential pipeline execution."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        # Mock execute_agent_task to return success
        mock_agent_result = {"status": "success", "run_id": 123, "duration_ms": 100}

        with patch("app.tasks.scheduler.get_db_session", _get_db_session):
            with patch("app.tasks.scheduler.execute_agent_task", return_value=mock_agent_result):
                result = _run_sequential_pipeline(
                    tenant_id=1,
                    user_id=1,
                    run_id=1,
                )

        assert result["status"] == "success"
        assert len(result["agents"]) == len(AGENT_ORDER)
        for agent in AGENT_ORDER:
            assert result["agents"][agent]["status"] == "success"

    def test_run_sequential_pipeline_failure_stops_chain(self, isolated_session_factory):
        """Test that agent failure stops the pipeline chain."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        # Mock execute_agent_task to fail on sales agent
        call_count = {"count": 0}

        def mock_execute(agent_name, tenant_id, user_id):
            call_count["count"] += 1
            if agent_name == "sales":
                return {"status": "failed", "error": "Sales failed"}
            return {"status": "success", "run_id": 123, "duration_ms": 100}

        with patch("app.tasks.scheduler.get_db_session", _get_db_session):
            with patch("app.tasks.scheduler.execute_agent_task", side_effect=mock_execute):
                result = _run_sequential_pipeline(
                    tenant_id=1,
                    user_id=1,
                    run_id=1,
                )

        # SDR should succeed, Sales should fail, rest should not run
        assert result["status"] == "failed"
        assert result["failed_at"] == "sales"
        assert result["agents"]["sdr"]["status"] == "success"
        assert result["agents"]["sales"]["status"] == "failed"
        # Negotiation and Finance should not be in results
        assert "negotiation" not in result["agents"]
        assert "finance" not in result["agents"]

    def test_run_sequential_pipeline_exception_handling(self, isolated_session_factory):
        """Test that exceptions are caught and handled."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        def mock_execute_raises(agent_name, tenant_id, user_id):
            if agent_name == "sdr":
                raise RuntimeError("SDR crashed")
            return {"status": "success"}

        with patch("app.tasks.scheduler.get_db_session", _get_db_session):
            with patch("app.tasks.scheduler.execute_agent_task", side_effect=mock_execute_raises):
                result = _run_sequential_pipeline(
                    tenant_id=1,
                    user_id=1,
                    run_id=1,
                )

        assert result["status"] == "failed"
        assert result["failed_at"] == "sdr"
        assert "error" in result


class TestAutomatedPipelineTask:
    """Tests for the main automated pipeline task."""

    def test_task_skipped_when_disabled(self, mock_disabled_config):
        """Test that task is skipped when pipeline is disabled."""
        with patch("app.tasks.scheduler.get_config", return_value=mock_disabled_config):
            result = automated_pipeline_run_task()

        assert result["status"] == "skipped"
        assert "AUTO_PIPELINE_ENABLED is False" in result["reason"]

    def test_task_skipped_on_concurrent_run(self, mock_config, isolated_session_factory):
        """Test that task is skipped when another run is active."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        # Create an active run
        session = isolated_session_factory()
        active_run = AgentRun(
            tenant_id=1,
            agent_name="automated_pipeline",
            task_id="existing-task",
            status="running",
            triggered_by="scheduler",
        )
        session.add(active_run)
        session.commit()

        with patch("app.tasks.scheduler.get_config", return_value=mock_config):
            with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                result = automated_pipeline_run_task()

        assert result["status"] == "skipped"
        assert "Active pipeline run already in progress" in result["reason"]

    def test_task_pipeline_skipped_when_no_new_leads(self, mock_config, isolated_session_factory):
        """Test that pipeline is skipped when no new leads are acquired."""
        from contextlib import contextmanager
        from datetime import datetime, timezone

        from app.schemas.scraper import ScraperResult

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        # Mock acquisition service to return no new leads (ScraperResult object)
        mock_acquisition_result = ScraperResult(
            correlation_id="test-correlation-id",
            tenant_id=1,
            started_at=datetime.now(timezone.utc),
            leads_inserted=0,
            leads_duplicate=5,
            leads_rejected=0,
        )

        with patch("app.tasks.scheduler.get_config", return_value=mock_config):
            with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                with patch("app.tasks.scheduler.LeadScraperService") as MockService:
                    mock_service = MockService.return_value
                    mock_service.acquire_and_persist.return_value = mock_acquisition_result

                    result = automated_pipeline_run_task()

        assert result["status"] == "success"
        assert result["pipeline"]["status"] == "skipped"
        assert "No new leads acquired" in result["pipeline"]["reason"]


class TestSchedulerStatus:
    """Tests for scheduler status endpoint."""

    def test_get_scheduler_status_disabled(self, mock_disabled_config, isolated_session_factory):
        """Test scheduler status when pipeline is disabled."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        with patch("app.tasks.scheduler.get_config", return_value=mock_disabled_config):
            with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                status = get_scheduler_status()

        assert status["enabled"] is False
        assert status["interval_hours"] == 6
        assert status["tenant_id"] == 1

    def test_get_scheduler_status_enabled(self, mock_config, isolated_session_factory):
        """Test scheduler status when pipeline is enabled."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db_session():
            session = isolated_session_factory()
            try:
                yield session
            finally:
                session.close()

        with patch("app.tasks.scheduler.get_config", return_value=mock_config):
            with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                status = get_scheduler_status()

        assert status["enabled"] is True
        assert status["interval_hours"] == 6

    def test_get_scheduler_status_with_last_run(self, mock_config, isolated_session_factory):
        """Test scheduler status includes last run info."""
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
            task_id="past-task",
            status="success",
            triggered_by="scheduler",
        )
        session.add(past_run)
        session.commit()

        with patch("app.tasks.scheduler.get_config", return_value=mock_config):
            with patch("app.tasks.scheduler.get_db_session", _get_db_session):
                status = get_scheduler_status()

        assert status["last_run"] is not None
        assert status["last_run"]["status"] == "success"


class TestDuplicateLeadPrevention:
    """Tests for duplicate lead prevention in acquisition."""

    def test_duplicate_lead_skipped(self, isolated_session_factory):
        """Test that duplicate leads are skipped during acquisition."""
        from contextlib import contextmanager

        from app.services.lead_scraper_service import LeadScraperService

        # Create an existing lead
        session = isolated_session_factory()
        existing_lead = Lead(
            tenant_id=1,
            name="Existing Contact",
            email="existing@example.com",
            company="Existing Co",
            status="New",
            source="manual",
        )
        session.add(existing_lead)
        session.commit()

        @contextmanager
        def _get_db_session():
            try:
                yield session
            finally:
                pass

        # Patch the service's get_db_session to use our test session
        with patch("app.services.lead_scraper_service.get_db_session", _get_db_session):
            service = LeadScraperService(tenant_id=1)
            # Test the _is_duplicate method - it only takes email as parameter
            is_dup = service._is_duplicate("existing@example.com")
            assert is_dup is True

            # Test with a non-duplicate email
            is_not_dup = service._is_duplicate("new@example.com")
            assert is_not_dup is False
