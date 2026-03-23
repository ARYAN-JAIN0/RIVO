"""LLM Router for multi-model routing in RIVO.

Routes tasks to appropriate models based on task type:
- DeepSeek: Reasoning tasks (sales_strategy, negotiation)
- Qwen: Generation tasks (email_generation, finance)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config_llm import (
    AGENT_MODEL_MAP,
    TASK_TYPE_MAP,
    get_llm_config,
)

if TYPE_CHECKING:
    from app.llm.clients import BaseLLMClient

logger = logging.getLogger(__name__)


class LLMRouter:
    """Routes LLM requests to appropriate models based on task type."""

    def __init__(self):
        self.config = get_llm_config()
        self.task_map = TASK_TYPE_MAP
        self.agent_map = AGENT_MODEL_MAP

    def route_by_task(self, task_type: str) -> str:
        """Route by task type.
        
        Args:
            task_type: Type of task (email_generation, sales_reasoning, etc.)
            
        Returns:
            Model name ('qwen' or 'deepseek')
        """
        model = self.task_map.get(task_type, self.config.DEFAULT_MODEL)
        logger.debug(
            "llm.router.task_route",
            extra={
                "event": "llm.router.task_route",
                "task_type": task_type,
                "model": model,
            },
        )
        return model

    def route_by_agent(self, agent_name: str) -> str:
        """Route by agent name.
        
        Args:
            agent_name: Name of the agent (sdr, sales, negotiation, finance)
            
        Returns:
            Model name ('qwen' or 'deepseek')
        """
        model = self.agent_map.get(agent_name, self.config.DEFAULT_MODEL)
        logger.debug(
            "llm.router.agent_route",
            extra={
                "event": "llm.router.agent_route",
                "agent": agent_name,
                "model": model,
            },
        )
        return model

    def get_model_for_request(self, agent_name: str | None = None, task_type: str | None = None) -> str:
        """Get model name for a request.
        
        Prefers agent_name over task_type if both provided.
        
        Args:
            agent_name: Name of the agent
            task_type: Type of the task
            
        Returns:
            Model name ('qwen' or 'deepseek')
        """
        if agent_name:
            return self.route_by_agent(agent_name)
        if task_type:
            return self.route_by_task(task_type)
        return self.config.DEFAULT_MODEL


# Global router instance
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Get the global router instance."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


def get_model_for_agent(agent_name: str) -> str:
    """Convenience function to get model for an agent."""
    return get_router().route_by_agent(agent_name)


def get_model_for_task(task_type: str) -> str:
    """Convenience function to get model for a task type."""
    return get_router().route_by_task(task_type)
