#!/usr/bin/env python
"""
RIVO Automated Pipeline Scheduler

This script runs the automated lead acquisition and pipeline execution system.
It will:
1. Scrape new leads every N hours (configurable via AUTO_PIPELINE_INTERVAL_HOURS)
2. Persist leads to database with status="New"
3. Run the full pipeline: SDR → Sales → Negotiation → Finance

Usage:
    python run_scheduler.py

Environment Variables:
    AUTO_PIPELINE_ENABLED     - Set to "True" to enable (default: True for this script)
    AUTO_PIPELINE_INTERVAL_HOURS - Hours between runs (default: 6)
    AUTO_PIPELINE_TENANT_ID   - Tenant ID for leads (default: 1)

To stop the scheduler: Press Ctrl+C
"""

from __future__ import annotations

import os
import sys
import time
import logging
from datetime import datetime
from signal import signal, SIGINT

# Enable the pipeline before importing the scheduler module
os.environ.setdefault("AUTO_PIPELINE_ENABLED", "True")
os.environ.setdefault("AUTO_PIPELINE_INTERVAL_HOURS", "6")
os.environ.setdefault("AUTO_PIPELINE_TENANT_ID", "1")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scheduler.log"),
    ],
)
logger = logging.getLogger(__name__)

# Import after environment variables are set
from app.tasks.scheduler import automated_pipeline_run_task, get_scheduler_status
from app.database.db import get_db_session
from app.database.models import Lead, AgentRun

# Flag for graceful shutdown
running = True


def handle_shutdown(signum, frame):
    """Handle Ctrl+C gracefully."""
    global running
    print("\n\nShutting down scheduler...")
    running = False


def print_banner():
    """Print startup banner."""
    print("\n" + "=" * 60)
    print("   RIVO Automated Pipeline Scheduler")
    print("=" * 60)


def print_status():
    """Print current scheduler status."""
    status = get_scheduler_status()
    print(f"\nConfiguration:")
    print(f"  Enabled:     {status['enabled']}")
    print(f"  Interval:    {status['interval_hours']} hours")
    print(f"  Tenant ID:   {status['tenant_id']}")
    if status.get("last_run"):
        print(f"\nLast Run:")
        print(f"  Status:      {status['last_run']['status']}")
        if status['last_run'].get('started_at'):
            print(f"  Started:     {status['last_run']['started_at']}")
        if status['last_run'].get('finished_at'):
            print(f"  Finished:    {status['last_run']['finished_at']}")
        if status['last_run'].get('error_message'):
            print(f"  Error:       {status['last_run']['error_message']}")
    else:
        print("\nLast Run: None (first run)")
    print("=" * 60 + "\n")


def get_lead_count():
    """Get current lead count from database."""
    try:
        with get_db_session() as session:
            return session.query(Lead).count()
    except Exception:
        return "N/A"


def get_recent_runs(limit=3):
    """Get recent pipeline runs."""
    try:
        with get_db_session() as session:
            runs = (
                session.query(AgentRun)
                .filter(AgentRun.agent_name == "automated_pipeline")
                .order_by(AgentRun.created_at.desc())
                .limit(limit)
                .all()
            )
            return runs
    except Exception:
        return []


def run_pipeline():
    """Execute the automated pipeline and return results."""
    logger.info("Starting automated pipeline run...")
    start_time = time.time()

    try:
        result = automated_pipeline_run_task()
        duration = time.time() - start_time

        logger.info(f"Pipeline completed in {duration:.2f} seconds")
        return result
    except Exception as e:
        logger.exception(f"Pipeline failed with error: {e}")
        return {"status": "error", "error": str(e)}


def print_result(result):
    """Print pipeline result summary."""
    print(f"\n{'-' * 40}")
    print(f"Pipeline Result:")
    print(f"  Status: {result.get('status', 'unknown')}")

    if "acquisition" in result:
        acq = result["acquisition"]
        print(f"\n  Lead Acquisition:")
        print(f"    Created:  {acq.get('created', 0)}")
        print(f"    Skipped:  {acq.get('skipped', 0)}")
        print(f"    Duplicates: {acq.get('skipped_duplicates', 0)}")
        print(f"    Invalid:  {acq.get('skipped_invalid', 0)}")
        print(f"    Daily Cap: {acq.get('daily_cap', 'N/A')}")

    if "pipeline" in result:
        pipe = result["pipeline"]
        print(f"\n  Pipeline Execution:")
        print(f"    Status: {pipe.get('status', 'unknown')}")
        if pipe.get("failed_at"):
            print(f"    Failed at: {pipe['failed_at']}")
            print(f"    Error: {pipe.get('error', 'unknown')}")

    if "run_id" in result:
        print(f"\n  Run ID: {result['run_id']}")

    if "duration_seconds" in result:
        print(f"  Duration: {result['duration_seconds']:.2f}s")

    print(f"{'-' * 40}\n")


def main():
    """Main scheduler loop."""
    global running

    # Setup signal handler for graceful shutdown
    signal(SIGINT, handle_shutdown)

    print_banner()
    print_status()

    status = get_scheduler_status()
    interval_seconds = status["interval_hours"] * 3600

    print(f"Scheduler started. Press Ctrl+C to stop.")
    print(f"Next run in {status['interval_hours']} hours (or after first run below)\n")

    run_count = 0

    while running:
        run_count += 1
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"\n{'=' * 60}")
        print(f"  Run #{run_count} - {current_time}")
        print(f"{'=' * 60}")

        # Show current lead count
        lead_count = get_lead_count()
        print(f"Current total leads in database: {lead_count}")

        # Run the pipeline
        result = run_pipeline()
        print_result(result)

        # Show updated lead count
        new_lead_count = get_lead_count()
        print(f"Updated total leads in database: {new_lead_count}")

        if not running:
            break

        # Calculate next run time
        next_run = datetime.now().timestamp() + interval_seconds
        next_run_str = datetime.fromtimestamp(next_run).strftime("%Y-%m-%d %H:%M:%S")

        print(f"\nNext run scheduled at: {next_run_str}")
        print(f"Waiting {status['interval_hours']} hours... (Press Ctrl+C to stop)")

        # Sleep in small increments to allow graceful shutdown
        sleep_remaining = interval_seconds
        while sleep_remaining > 0 and running:
            sleep_time = min(60, sleep_remaining)  # Check every minute
            time.sleep(sleep_time)
            sleep_remaining -= sleep_time

    print("\nScheduler stopped. Goodbye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
