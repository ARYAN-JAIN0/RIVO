from __future__ import annotations

from app.services.run_service import RunService


def test_run_service_register_and_update():
    service = RunService()
    record = service.register("run-1", "agents.sdr")
    assert record.status == "queued"

    updated = service.update_status("run-1", "failed", retry_count=2, error_payload={"error": "boom"})
    assert updated is not None
    assert updated.status == "failed"
    assert updated.retry_count == 2
    assert updated.error_payload == {"error": "boom"}
