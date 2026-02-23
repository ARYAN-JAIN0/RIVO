"""Automated pipeline scheduler for recurring lead acquisition and pipeline execution.

This module provides the automated recurring task that:
1. Scrapes new leads using LeadScraperService (production-hardened)
2. Persists leads to database (status=New)
3. Triggers sequential pipeline execution (SDR → Sales → Negotiation → Finance)

The scheduler is controlled by environment variables:
- AUTO_PIPELINE_ENABLED: Set to "true" to enable automated runs (default: false)
- AUTO_PIPELINE_INTERVAL_HOURS: Interval in hours between runs (default: 6)
- AUTO_LEAD_SCRAPE_INTERVAL_HOURS: Interval for lead scraping (default: 1)

Tasks:
- scrape_leads_task: Fetches and validates leads from configured sources
- run_pipeline_task: Executes the SDR → Sales → Negotiation → Finance pipeline
- automated_pipeline_run_task: Combined scrape + pipeline (legacy compatibility)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_config
from app.database.db import get_db_session
from app.database.models import AgentRun
from app.services.lead_scraper_service import LeadScraperService
from app.tasks.agent_tasks import execute_agent_task
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Agent execution order for sequential pipeline
AGENT_ORDER = ["sdr", "sales", "negotiation", "finance"]


def _is_pipeline_enabled() -> bool:
    """Check if automated pipeline is enabled via configuration."""
    config = get_config()
    return config.AUTO_PIPELINE_ENABLED


def _get_tenant_id() -> int:
    """Get the tenant ID for automated pipeline runs."""
    config = get_config()
    return config.AUTO_PIPELINE_TENANT_ID


def _check_active_pipeline_run(tenant_id: int) -> bool:
    """Check if there's already an active pipeline run for the tenant.

    Returns True if there's an active run, False otherwise.
    """
    with get_db_session() as session:
        active_run = (
            session.query(AgentRun)
            .filter(AgentRun.tenant_id == tenant_id)
            .filter(AgentRun.agent_name == "automated_pipeline")
            .filter(AgentRun.status.in_(["queued", "running"]))
            .first()
        )
        return active_run is not None


def _create_pipeline_run_record(tenant_id: int, task_id: str | None = None) -> int:
    """Create a new pipeline run record in the database.

    Returns the ID of the created record.
    """
    with get_db_session() as session:
        run = AgentRun(
            tenant_id=tenant_id,
            agent_name="automated_pipeline",
            task_id=task_id,
            status="running",
            triggered_by="scheduler",
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run.id


def _update_pipeline_run_status(run_id: int, status: str, error_message: str | None = None) -> None:
    """Update the status of a pipeline run record."""
    with get_db_session() as session:
        run = session.query(AgentRun).filter(AgentRun.id == run_id).first()
        if run:
            run.status = status
            run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
            if error_message:
                run.error_message = error_message
            session.commit()


def _run_sequential_pipeline(tenant_id: int, user_id: int, run_id: int) -> dict[str, Any]:
    """Run agents sequentially with failure propagation.

    Each agent must succeed before the next one runs.
    If any agent fails, the chain stops and the error is logged.

    Args:
        tenant_id: Tenant ID for the pipeline run
        user_id: User ID for the pipeline run
        run_id: Pipeline run record ID for tracking

    Returns:
        Dict with results for each agent and overall status
    """
    results: dict[str, Any] = {
        "agents": {},
        "status": "success",
        "failed_at": None,
    }

    for agent_name in AGENT_ORDER:
        logger.info(
            "automated_pipeline.agent.start",
            extra={
                "event": "automated_pipeline.agent.start",
                "agent": agent_name,
                "run_id": run_id,
                "tenant_id": tenant_id,
            },
        )

        try:
            # Execute the agent task synchronously (using apply instead of delay)
            # This ensures sequential execution with proper error handling
            result = execute_agent_task(
                agent_name=agent_name,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            agent_status = result.get("status", "unknown")
            results["agents"][agent_name] = {
                "status": agent_status,
                "run_id": result.get("run_id"),
                "duration_ms": result.get("duration_ms"),
            }

            if agent_status != "success":
                # Agent failed - stop the chain
                results["status"] = "failed"
                results["failed_at"] = agent_name
                results["error"] = result.get("error", "Unknown error")

                logger.error(
                    "automated_pipeline.agent.failed",
                    extra={
                        "event": "automated_pipeline.agent.failed",
                        "agent": agent_name,
                        "run_id": run_id,
                        "error": results["error"],
                    },
                )
                break

            logger.info(
                "automated_pipeline.agent.success",
                extra={
                    "event": "automated_pipeline.agent.success",
                    "agent": agent_name,
                    "run_id": run_id,
                    "duration_ms": result.get("duration_ms"),
                },
            )

        except Exception as exc:
            # Unexpected error - stop the chain
            results["status"] = "failed"
            results["failed_at"] = agent_name
            results["error"] = str(exc)
            results["agents"][agent_name] = {"status": "error", "error": str(exc)}

            logger.exception(
                "automated_pipeline.agent.exception",
                extra={
                    "event": "automated_pipeline.agent.exception",
                    "agent": agent_name,
                    "run_id": run_id,
                },
            )
            break

    return results


@celery_app.task(name="tasks.automated_pipeline_run")
def automated_pipeline_run_task(tenant_id: int | None = None, user_id: int = 1) -> dict[str, Any]:
    """Main automated pipeline task that runs on schedule.

    This task:
    1. Checks if automated pipeline is enabled
    2. Acquires and persists new leads
    3. Triggers sequential pipeline execution

    Args:
        tenant_id: Optional tenant ID (defaults to config value)
        user_id: User ID for the pipeline run (default: 1)

    Returns:
        Dict with acquisition results and pipeline execution status
    """
    job_start = datetime.now(timezone.utc)

    # Check if pipeline is enabled
    if not _is_pipeline_enabled():
        logger.info(
            "automated_pipeline.disabled",
            extra={
                "event": "automated_pipeline.disabled",
                "timestamp": job_start.isoformat(),
            },
        )
        return {
            "status": "skipped",
            "reason": "AUTO_PIPELINE_ENABLED is False",
            "timestamp": job_start.isoformat(),
        }

    # Resolve tenant ID
    resolved_tenant_id = tenant_id or _get_tenant_id()

    # Check for concurrent runs
    if _check_active_pipeline_run(resolved_tenant_id):
        logger.warning(
            "automated_pipeline.concurrent_run_detected",
            extra={
                "event": "automated_pipeline.concurrent_run_detected",
                "tenant_id": resolved_tenant_id,
                "timestamp": job_start.isoformat(),
            },
        )
        return {
            "status": "skipped",
            "reason": "Active pipeline run already in progress",
            "tenant_id": resolved_tenant_id,
            "timestamp": job_start.isoformat(),
        }

    # Create pipeline run record
    task_id = automated_pipeline_run_task.request.id if hasattr(automated_pipeline_run_task, "request") else None
    run_id = _create_pipeline_run_record(resolved_tenant_id, task_id)

    logger.info(
        "automated_pipeline.started",
        extra={
            "event": "automated_pipeline.started",
            "run_id": run_id,
            "tenant_id": resolved_tenant_id,
            "timestamp": job_start.isoformat(),
        },
    )

    result: dict[str, Any] = {
        "run_id": run_id,
        "tenant_id": resolved_tenant_id,
        "started_at": job_start.isoformat(),
    }

    try:
        # Step 1: Acquire and persist leads using production-hardened scraper
        scraper_service = LeadScraperService(tenant_id=resolved_tenant_id)
        scraper_result = scraper_service.acquire_and_persist()

        acquisition_result = {
            "created": scraper_result.leads_inserted,
            "skipped": scraper_result.leads_duplicate,
            "rejected": scraper_result.leads_rejected,
            "rejections": [
                {"reason": r.rejection_reason, "detail": r.rejection_detail}
                for r in scraper_result.rejections
            ],
        }
        result["acquisition"] = acquisition_result

        logger.info(
            "automated_pipeline.acquisition.complete",
            extra={
                "event": "automated_pipeline.acquisition.complete",
                "run_id": run_id,
                "leads_created": scraper_result.leads_inserted,
                "leads_skipped": scraper_result.leads_duplicate,
                "leads_rejected": scraper_result.leads_rejected,
            },
        )

        # Step 2: Run sequential pipeline if leads were acquired
        if scraper_result.leads_inserted > 0:
            pipeline_result = _run_sequential_pipeline(
                tenant_id=resolved_tenant_id,
                user_id=user_id,
                run_id=run_id,
            )
            result["pipeline"] = pipeline_result
            result["status"] = pipeline_result["status"]

            if pipeline_result["status"] == "success":
                _update_pipeline_run_status(run_id, "success")
            else:
                _update_pipeline_run_status(run_id, "failed", pipeline_result.get("error"))
        else:
            # No new leads - mark as success but note no pipeline run
            result["pipeline"] = {"status": "skipped", "reason": "No new leads acquired"}
            result["status"] = "success"
            _update_pipeline_run_status(run_id, "success")

    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)

        logger.exception(
            "automated_pipeline.failed",
            extra={
                "event": "automated_pipeline.failed",
                "run_id": run_id,
                "error": str(exc),
            },
        )

        _update_pipeline_run_status(run_id, "failed", str(exc))

    job_end = datetime.now(timezone.utc)
    result["completed_at"] = job_end.isoformat()
    result["duration_seconds"] = (job_end - job_start).total_seconds()

    logger.info(
        "automated_pipeline.complete",
        extra={
            "event": "automated_pipeline.complete",
            "run_id": run_id,
            "status": result["status"],
            "duration_seconds": result["duration_seconds"],
        },
    )

    return result


@celery_app.task(name="tasks.scrape_leads")
def scrape_leads_task(
    tenant_id: int | None = None,
    sources: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Scrape and validate leads from configured sources.

    This task uses the production-hardened LeadScraperService which:
    - Validates all leads against ScrapedLeadSchema
    - Rejects generic email providers (gmail.com, yahoo.com, etc.)
    - Enforces domain alignment (email domain must match company domain)
    - Deduplicates against existing database records
    - Logs structured rejection reasons for observability

    Args:
        tenant_id: Optional tenant ID (defaults to AUTO_PIPELINE_TENANT_ID)
        sources: Optional list of source configurations to scrape

    Returns:
        Dict with scraping results:
        - leads_created: Number of leads successfully persisted
        - leads_rejected: Number of leads rejected during validation
        - leads_duplicate: Number of leads skipped as duplicates
        - rejections: List of rejection reasons with counts
    """
    job_start = datetime.now(timezone.utc)
    resolved_tenant_id = tenant_id or _get_tenant_id()

    logger.info(
        "scrape_leads.started",
        extra={
            "event": "scrape_leads.started",
            "tenant_id": resolved_tenant_id,
            "timestamp": job_start.isoformat(),
        },
    )

    result: dict[str, Any] = {
        "tenant_id": resolved_tenant_id,
        "started_at": job_start.isoformat(),
    }

    try:
        scraper_service = LeadScraperService(tenant_id=resolved_tenant_id)
        scraper_result = scraper_service.acquire_and_persist(sources=sources)

        result["leads_created"] = scraper_result.created_count
        result["leads_rejected"] = scraper_result.rejected_count
        result["leads_duplicate"] = scraper_result.duplicate_count
        result["rejections"] = [
            {"reason": r.reason, "count": r.count}
            for r in scraper_result.rejections
        ]
        result["status"] = "success"

        logger.info(
            "scrape_leads.complete",
            extra={
                "event": "scrape_leads.complete",
                "tenant_id": resolved_tenant_id,
                "leads_created": scraper_result.created_count,
                "leads_rejected": scraper_result.rejected_count,
                "leads_duplicate": scraper_result.duplicate_count,
            },
        )

    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)

        logger.exception(
            "scrape_leads.failed",
            extra={
                "event": "scrape_leads.failed",
                "tenant_id": resolved_tenant_id,
                "error": str(exc),
            },
        )

    job_end = datetime.now(timezone.utc)
    result["completed_at"] = job_end.isoformat()
    result["duration_seconds"] = (job_end - job_start).total_seconds()

    return result


@celery_app.task(name="tasks.run_pipeline")
def run_pipeline_task(
    tenant_id: int | None = None,
    user_id: int = 1,
) -> dict[str, Any]:
    """Execute the sequential agent pipeline (SDR → Sales → Negotiation → Finance).

    This task runs the agent pipeline on existing leads with status="New".
    It does NOT acquire new leads - use scrape_leads_task for that.

    Args:
        tenant_id: Optional tenant ID (defaults to AUTO_PIPELINE_TENANT_ID)
        user_id: User ID for the pipeline run (default: 1)

    Returns:
        Dict with pipeline execution results
    """
    job_start = datetime.now(timezone.utc)

    if not _is_pipeline_enabled():
        logger.info(
            "run_pipeline.disabled",
            extra={
                "event": "run_pipeline.disabled",
                "timestamp": job_start.isoformat(),
            },
        )
        return {
            "status": "skipped",
            "reason": "AUTO_PIPELINE_ENABLED is False",
            "timestamp": job_start.isoformat(),
        }

    resolved_tenant_id = tenant_id or _get_tenant_id()

    # Check for concurrent runs
    if _check_active_pipeline_run(resolved_tenant_id):
        logger.warning(
            "run_pipeline.concurrent_run_detected",
            extra={
                "event": "run_pipeline.concurrent_run_detected",
                "tenant_id": resolved_tenant_id,
                "timestamp": job_start.isoformat(),
            },
        )
        return {
            "status": "skipped",
            "reason": "Active pipeline run already in progress",
            "tenant_id": resolved_tenant_id,
            "timestamp": job_start.isoformat(),
        }

    # Create pipeline run record
    task_id = run_pipeline_task.request.id if hasattr(run_pipeline_task, "request") else None
    run_id = _create_pipeline_run_record(resolved_tenant_id, task_id)

    logger.info(
        "run_pipeline.started",
        extra={
            "event": "run_pipeline.started",
            "run_id": run_id,
            "tenant_id": resolved_tenant_id,
            "timestamp": job_start.isoformat(),
        },
    )

    result: dict[str, Any] = {
        "run_id": run_id,
        "tenant_id": resolved_tenant_id,
        "started_at": job_start.isoformat(),
    }

    try:
        pipeline_result = _run_sequential_pipeline(
            tenant_id=resolved_tenant_id,
            user_id=user_id,
            run_id=run_id,
        )
        result["pipeline"] = pipeline_result
        result["status"] = pipeline_result["status"]

        if pipeline_result["status"] == "success":
            _update_pipeline_run_status(run_id, "success")
        else:
            _update_pipeline_run_status(run_id, "failed", pipeline_result.get("error"))

    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)

        logger.exception(
            "run_pipeline.failed",
            extra={
                "event": "run_pipeline.failed",
                "run_id": run_id,
                "error": str(exc),
            },
        )

        _update_pipeline_run_status(run_id, "failed", str(exc))

    job_end = datetime.now(timezone.utc)
    result["completed_at"] = job_end.isoformat()
    result["duration_seconds"] = (job_end - job_start).total_seconds()

    logger.info(
        "run_pipeline.complete",
        extra={
            "event": "run_pipeline.complete",
            "run_id": run_id,
            "status": result["status"],
            "duration_seconds": result["duration_seconds"],
        },
    )

    return result


@celery_app.task(name="tasks.scrape_and_run_pipeline")
def scrape_and_run_pipeline_task(
    tenant_id: int | None = None,
    user_id: int = 1,
) -> dict[str, Any]:
    """Combined task that scrapes leads then runs the pipeline.

    This task chains scrape_leads_task and run_pipeline_task.
    The pipeline only runs if leads were successfully created.

    Args:
        tenant_id: Optional tenant ID (defaults to AUTO_PIPELINE_TENANT_ID)
        user_id: User ID for the pipeline run (default: 1)

    Returns:
        Dict with combined scraping and pipeline results
    """
    job_start = datetime.now(timezone.utc)
    resolved_tenant_id = tenant_id or _get_tenant_id()

    result: dict[str, Any] = {
        "tenant_id": resolved_tenant_id,
        "started_at": job_start.isoformat(),
    }

    # Step 1: Scrape leads
    scrape_result = scrape_leads_task(tenant_id=resolved_tenant_id)
    result["scrape"] = scrape_result

    # Step 2: Run pipeline if leads were created and pipeline is enabled
    if scrape_result.get("status") == "success" and scrape_result.get("leads_created", 0) > 0:
        if _is_pipeline_enabled():
            pipeline_result = run_pipeline_task(tenant_id=resolved_tenant_id, user_id=user_id)
            result["pipeline"] = pipeline_result
            result["status"] = pipeline_result.get("status", "unknown")
        else:
            result["pipeline"] = {"status": "skipped", "reason": "AUTO_PIPELINE_ENABLED is False"}
            result["status"] = "success"
    elif scrape_result.get("status") != "success":
        result["status"] = "failed"
        result["error"] = f"Scraping failed: {scrape_result.get('error', 'Unknown error')}"
    else:
        result["pipeline"] = {"status": "skipped", "reason": "No new leads created"}
        result["status"] = "success"

    job_end = datetime.now(timezone.utc)
    result["completed_at"] = job_end.isoformat()
    result["duration_seconds"] = (job_end - job_start).total_seconds()

    return result


def get_scheduler_status() -> dict[str, Any]:
    """Get the current status of the automated pipeline scheduler.

    Returns:
        Dict with scheduler configuration and recent run info
    """
    config = get_config()

    with get_db_session() as session:
        last_run = (
            session.query(AgentRun)
            .filter(AgentRun.agent_name == "automated_pipeline")
            .order_by(AgentRun.created_at.desc())
            .first()
        )

        return {
            "enabled": config.AUTO_PIPELINE_ENABLED,
            "interval_hours": config.AUTO_PIPELINE_INTERVAL_HOURS,
            "tenant_id": config.AUTO_PIPELINE_TENANT_ID,
            "last_run": {
                "id": last_run.id if last_run else None,
                "status": last_run.status if last_run else None,
                "started_at": last_run.started_at.isoformat() if last_run and last_run.started_at else None,
                "finished_at": last_run.finished_at.isoformat() if last_run and last_run.finished_at else None,
                "error_message": last_run.error_message if last_run else None,
            } if last_run else None,
        }
