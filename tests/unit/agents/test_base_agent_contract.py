from __future__ import annotations

from app.agents.base_agent import AgentResult, BaseAgent


class DummyAgent(BaseAgent):
    name = "dummy"

    def run(self, context: dict) -> AgentResult:
        return AgentResult(agent_name=self.name, status="success", run_id=context.get("run_id"))


def test_base_agent_contract_returns_agent_result():
    agent = DummyAgent()
    result = agent.run({"run_id": "r1"})
    assert result.agent_name == "dummy"
    assert result.status == "success"
    assert result.run_id == "r1"
