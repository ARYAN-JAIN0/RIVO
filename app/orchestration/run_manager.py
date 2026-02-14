"""Run manager for allocating and tracking run identifiers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock


@dataclass
class ManagedRun:
    run_id: str
    created_at: str
    status: str = "queued"


class RunManager:
    """Small run-id manager to provide idempotent identifiers."""

    def __init__(self) -> None:
        self._runs: dict[str, ManagedRun] = {}
        self._lock = Lock()

    def create_run(self) -> ManagedRun:
        with self._lock:
            run_id = str(uuid.uuid4())
            run = ManagedRun(run_id=run_id, created_at=datetime.now(timezone.utc).isoformat())
            self._runs[run_id] = run
            return run

    def mark_status(self, run_id: str, status: str) -> ManagedRun | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            run.status = status
            return run

    def get_run(self, run_id: str) -> ManagedRun | None:
        with self._lock:
            return self._runs.get(run_id)

