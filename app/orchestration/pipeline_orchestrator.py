"""Class-based pipeline orchestrator contract for API/queue execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.agents.base_agent import AgentResult, BaseAgent
from app.orchestration.run_manager import RunManager


@dataclass
class PipelineResult:
    run_id: str
    results: list[AgentResult]


class PipelineOrchestrator:
    """Execute a sequence of agents under a shared run context."""

    def __init__(self, run_manager: RunManager | None = None) -> None:
        self.run_manager = run_manager or RunManager()

    def run(self, agents: Iterable[BaseAgent], context: dict) -> PipelineResult:
        managed = self.run_manager.create_run()
        run_context = dict(context)
        run_context["run_id"] = managed.run_id
        results = [agent.run(run_context) for agent in agents]
        self.run_manager.mark_status(managed.run_id, "completed")
        return PipelineResult(run_id=managed.run_id, results=results)

