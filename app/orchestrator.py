"""Central orchestrator for the multi-agent RIVO workflow."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.finance_agent import run_finance_agent
from app.agents.negotiation_agent import run_negotiation_agent
from app.agents.sales_agent import run_sales_agent
from app.agents.sdr_agent import run_sdr_agent
from app.core.enums import ContractStatus, DealStage, InvoiceStatus, LeadStatus
from app.core.startup import bootstrap
from app.database.db_handler import (
    fetch_contracts_by_status,
    fetch_deals_by_status,
    fetch_invoices_by_status,
    fetch_leads_by_status,
    fetch_pending_reviews,
)
from memory.graph_store import initialize_graph_store
from memory.vector_store import initialize_vector_store

logger = logging.getLogger(__name__)


class RevoOrchestrator:
    """Event-driven orchestrator for SDR -> Sales -> Negotiation -> Finance."""

    def __init__(self) -> None:
        self.agents = {
            "sdr": run_sdr_agent,
            "sales": run_sales_agent,
            "negotiation": run_negotiation_agent,
            "finance": run_finance_agent,
        }
        self.vector_store = initialize_vector_store()
        self.graph_store = initialize_graph_store()
        logger.info(
            "orchestrator.initialized",
            extra={
                "event": "orchestrator.initialized",
                "agents": ",".join(self.agents.keys()),
                "vector_store_enabled": bool(self.vector_store),
                "graph_store_enabled": bool(self.graph_store),
            },
        )

    def run_pipeline(self, agents_to_run: List[str] | None = None) -> Dict[str, str]:
        agents = agents_to_run or ["sdr", "sales", "negotiation", "finance"]
        results: Dict[str, str] = {}
        logger.info("orchestrator.pipeline.start", extra={"event": "orchestrator.pipeline.start", "agents": ",".join(agents)})

        for agent_name in agents:
            agent_fn = self.agents.get(agent_name)
            if not agent_fn:
                results[agent_name] = "unknown_agent"
                logger.warning("orchestrator.agent.unknown", extra={"event": "orchestrator.agent.unknown", "agent": agent_name})
                continue

            try:
                logger.info("orchestrator.agent.start", extra={"event": "orchestrator.agent.start", "agent": agent_name})
                agent_fn()
                results[agent_name] = "success"
                logger.info("orchestrator.agent.success", extra={"event": "orchestrator.agent.success", "agent": agent_name})
            except Exception as exc:
                results[agent_name] = f"error: {exc}"
                logger.exception(
                    "orchestrator.agent.failure",
                    extra={"event": "orchestrator.agent.failure", "agent": agent_name},
                )

        logger.info("orchestrator.pipeline.complete", extra={"event": "orchestrator.pipeline.complete", "results": json.dumps(results)})
        return results

    def run_single_agent(self, agent_name: str) -> Dict[str, str]:
        return self.run_pipeline(agents_to_run=[agent_name])

    def get_system_health(self) -> Dict:
        try:
            new_leads = fetch_leads_by_status(LeadStatus.NEW.value)
            pending_reviews = fetch_pending_reviews()
            contacted = fetch_leads_by_status(LeadStatus.CONTACTED.value)
            qualified = fetch_deals_by_status(DealStage.QUALIFIED.value)
            proposals = fetch_deals_by_status(DealStage.PROPOSAL_SENT.value)
            negotiating = fetch_contracts_by_status(ContractStatus.NEGOTIATING.value)
            overdue = fetch_invoices_by_status(InvoiceStatus.OVERDUE.value)

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sdr": {
                    "new_leads": len(new_leads),
                    "pending_review": len(pending_reviews),
                    "contacted": len(contacted),
                },
                "sales": {
                    "qualified": len(qualified),
                    "proposals_sent": len(proposals),
                },
                "negotiation": {"active_negotiations": len(negotiating)},
                "finance": {"overdue_invoices": len(overdue)},
            }
        except Exception as exc:
            logger.exception("orchestrator.health.failed", extra={"event": "orchestrator.health.failed"})
            return {"error": str(exc)}


def main() -> None:
    bootstrap()
    orchestrator = RevoOrchestrator()

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "health":
            print(json.dumps(orchestrator.get_system_health(), indent=2))
            return
        if command in orchestrator.agents:
            print(json.dumps(orchestrator.run_single_agent(command), indent=2))
            return

        print(json.dumps({"error": f"unknown command '{command}'", "available": list(orchestrator.agents.keys()) + ["health"]}, indent=2))
        return

    print(json.dumps(orchestrator.run_pipeline(), indent=2))


if __name__ == "__main__":
    main()
