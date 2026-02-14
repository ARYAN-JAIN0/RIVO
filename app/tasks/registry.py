"""Task registry mapping task keys to executable callables."""

from __future__ import annotations

from collections.abc import Callable

from app.agents.finance_agent import run_finance_agent
from app.agents.negotiation_agent import run_negotiation_agent
from app.agents.sales_agent import run_sales_agent
from app.agents.sdr_agent import run_sdr_agent
from app.orchestrator import RevoOrchestrator

TaskExecutor = Callable[[], None]


class TaskRegistry:
    """Mutable task registry for agent and pipeline tasks."""

    def __init__(self) -> None:
        self._executors: dict[str, TaskExecutor] = {}

    def register(self, task_key: str, executor: TaskExecutor) -> None:
        self._executors[task_key] = executor

    def get(self, task_key: str) -> TaskExecutor:
        if task_key not in self._executors:
            raise KeyError(f"Unknown task key: {task_key}")
        return self._executors[task_key]

    def keys(self) -> list[str]:
        return sorted(self._executors.keys())


def _run_pipeline() -> None:
    RevoOrchestrator().run_pipeline()


def build_default_registry() -> TaskRegistry:
    registry = TaskRegistry()
    registry.register("agents.sdr", run_sdr_agent)
    registry.register("agents.sales", run_sales_agent)
    registry.register("agents.negotiation", run_negotiation_agent)
    registry.register("agents.finance", run_finance_agent)
    registry.register("agents.pipeline", _run_pipeline)
    return registry


default_registry = build_default_registry()

