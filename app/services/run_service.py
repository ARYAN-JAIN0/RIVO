"""Run metadata service for orchestration and API list endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock


@dataclass
class RunRecord:
    run_id: str
    agent_name: str
    status: str
    created_at: str
    retry_count: int = 0
    finished_at: str | None = None
    error_payload: dict | None = None


class RunService:
    """In-memory run registry placeholder until DB-backed run tables land."""

    _records: dict[str, RunRecord] = {}
    _lock = Lock()

    def register(self, run_id: str, agent_name: str, status: str = "queued") -> RunRecord:
        with self._lock:
            record = RunRecord(
                run_id=run_id,
                agent_name=agent_name,
                status=status,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._records[run_id] = record
            return record

    def list_runs(self) -> list[RunRecord]:
        with self._lock:
            return list(self._records.values())

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._records.get(run_id)

    def update_status(
        self,
        run_id: str,
        status: str,
        retry_count: int | None = None,
        finished_at: str | None = None,
        error_payload: dict | None = None,
    ) -> RunRecord | None:
        with self._lock:
            record = self._records.get(run_id)
            if record is None:
                return None
            record.status = status
            if retry_count is not None:
                record.retry_count = retry_count
            if finished_at is not None:
                record.finished_at = finished_at
            if error_payload is not None:
                record.error_payload = error_payload
            return record
