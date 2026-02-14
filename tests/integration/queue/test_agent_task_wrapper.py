from __future__ import annotations

from app.tasks.agent_tasks import execute_registered_task
from app.tasks.registry import default_registry


def test_agent_task_retries_then_succeeds():
    state = {"calls": 0}

    def flaky_executor():
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("transient failure")

    default_registry.register("test.flaky", flaky_executor)
    result = execute_registered_task(
        task_key="test.flaky",
        tenant_id=1,
        user_id=1,
        max_retries=1,
        base_backoff_seconds=0.0,
    )
    assert result["status"] == "succeeded"
    assert result["retry_count"] == 1


def test_agent_task_unknown_key_dead_letters():
    result = execute_registered_task(
        task_key="test.missing",
        tenant_id=1,
        user_id=1,
        max_retries=0,
    )
    assert result["status"] == "failed"
    assert result["dead_lettered"] is True
