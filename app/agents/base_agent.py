"""Base contract for class-based agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Normalized output for agent executions."""

    agent_name: str
    status: str
    run_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class BaseAgent(ABC):
    """Agent contract used by orchestration and queue wrappers."""

    name: str = "base"

    @abstractmethod
    def run(self, context: dict[str, Any]) -> AgentResult:
        """Execute the agent and return a normalized result."""
        raise NotImplementedError

