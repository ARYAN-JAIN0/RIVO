from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.database.db import get_db_session
from app.database.models import AgentRun

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_stale_runs():
    """
    Finds any automated pipeline runs that are stuck in a 'running' state
    and updates their status to 'failed' so that new runs can proceed.
    """
    with get_db_session() as session:
        stale_runs = (
            session.query(AgentRun)
            .filter(AgentRun.agent_name == "automated_pipeline")
            .filter(AgentRun.status.in_(["queued", "running"]))
            .all()
        )

        if not stale_runs:
            logger.info("No stale pipeline runs found. Database is clean.")
            return

        logger.warning(f"Found {len(stale_runs)} stale run(s).")
        for run in stale_runs:
            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
            run.error_message = "Manually marked as failed due to being stale from a previous unclean shutdown."
            logger.info(f"  - Updated Run ID {run.id} (started at {run.started_at}) to 'failed'.")

        session.commit()
        logger.info("Stale runs have been successfully marked as 'failed'.")

if __name__ == "__main__":
    fix_stale_runs()
