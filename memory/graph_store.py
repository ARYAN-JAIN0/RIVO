"""Graph memory store with graceful degradation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import networkx as nx

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False


BASE_DIR = Path(__file__).resolve().parents[1]
GRAPH_STORE_PATH = BASE_DIR / "memory" / "graph_store.json"


class GraphStore:
    def __init__(self) -> None:
        if not NETWORKX_AVAILABLE:
            self.graph = None
            logger.info("graph_store.disabled_missing_dependency", extra={"event": "graph_store.disabled_missing_dependency"})
            return

        self.graph = nx.DiGraph()
        if GRAPH_STORE_PATH.exists():
            self._load_graph()
        logger.info("graph_store.initialized", extra={"event": "graph_store.initialized"})

    def add_lead(self, lead_id: int, metadata: Dict) -> None:
        if self.graph is None:
            return
        self.graph.add_node(f"lead_{lead_id}", node_type="lead", **metadata)

    def add_deal(self, deal_id: int, lead_id: int, metadata: Dict) -> None:
        if self.graph is None:
            return
        deal_node = f"deal_{deal_id}"
        lead_node = f"lead_{lead_id}"
        self.graph.add_node(deal_node, node_type="deal", **metadata)
        self.graph.add_edge(lead_node, deal_node, relationship="converted_to")

    def add_contract(self, contract_id: int, deal_id: int, metadata: Dict) -> None:
        if self.graph is None:
            return
        contract_node = f"contract_{contract_id}"
        deal_node = f"deal_{deal_id}"
        self.graph.add_node(contract_node, node_type="contract", **metadata)
        self.graph.add_edge(deal_node, contract_node, relationship="progressed_to")

    def add_invoice(self, invoice_id: int, contract_id: int, metadata: Dict) -> None:
        if self.graph is None:
            return
        invoice_node = f"invoice_{invoice_id}"
        contract_node = f"contract_{contract_id}"
        self.graph.add_node(invoice_node, node_type="invoice", **metadata)
        self.graph.add_edge(contract_node, invoice_node, relationship="invoiced")

    def add_company_relationship(self, company_name: str, lead_id: int) -> None:
        if self.graph is None:
            return
        company_node = f"company_{company_name.replace(' ', '_').lower()}"
        lead_node = f"lead_{lead_id}"
        if not self.graph.has_node(company_node):
            self.graph.add_node(company_node, node_type="company", name=company_name)
        self.graph.add_edge(company_node, lead_node, relationship="employee")

    def get_lead_journey(self, lead_id: int) -> List[Dict]:
        if self.graph is None:
            return []
        lead_node = f"lead_{lead_id}"
        if not self.graph.has_node(lead_node):
            return []

        visited = set()
        queue = [lead_node]
        journey = []
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            node_data = self.graph.nodes[node]
            journey.append({"node": node, "type": node_data.get("node_type"), "data": dict(node_data)})
            for successor in self.graph.successors(node):
                if successor not in visited:
                    queue.append(successor)
        return journey

    def find_conversion_patterns(self, min_deal_value: int = 50_000) -> Dict:
        if self.graph is None:
            return {}
        patterns = {
            "successful_industries": {},
            "successful_roles": {},
            "avg_time_to_close": 0,
            "conversion_rate": 0,
        }
        high_value_deals = [
            node
            for node, data in self.graph.nodes(data=True)
            if data.get("node_type") == "deal" and data.get("deal_value", 0) >= min_deal_value
        ]
        for deal_node in high_value_deals:
            predecessors = list(self.graph.predecessors(deal_node))
            if not predecessors:
                continue
            lead_data = self.graph.nodes[predecessors[0]]
            industry = lead_data.get("industry", "Unknown")
            role = lead_data.get("role", "Unknown")
            patterns["successful_industries"][industry] = patterns["successful_industries"].get(industry, 0) + 1
            patterns["successful_roles"][role] = patterns["successful_roles"].get(role, 0) + 1

        total_leads = sum(1 for _, data in self.graph.nodes(data=True) if data.get("node_type") == "lead")
        total_deals = sum(1 for _, data in self.graph.nodes(data=True) if data.get("node_type") == "deal")
        patterns["conversion_rate"] = round((total_deals / total_leads * 100), 1) if total_leads else 0
        return patterns

    def get_company_contacts(self, company_name: str) -> List[int]:
        if self.graph is None:
            return []
        company_node = f"company_{company_name.replace(' ', '_').lower()}"
        if not self.graph.has_node(company_node):
            return []
        lead_ids = []
        for successor in self.graph.successors(company_node):
            if successor.startswith("lead_"):
                lead_ids.append(int(successor.split("_")[1]))
        return lead_ids

    def get_stats(self) -> Dict:
        if self.graph is None:
            return {"error": "Graph not initialized"}
        node_counts = {}
        for _, data in self.graph.nodes(data=True):
            node_type = data.get("node_type", "unknown")
            node_counts[node_type] = node_counts.get(node_type, 0) + 1
        total_nodes = self.graph.number_of_nodes()
        total_edges = self.graph.number_of_edges()
        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "node_counts": node_counts,
            "avg_connections": round(total_edges / max(total_nodes, 1), 2),
        }

    def save_graph(self) -> None:
        if self.graph is None:
            return
        GRAPH_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        graph_data = nx.node_link_data(self.graph)
        with open(GRAPH_STORE_PATH, "w", encoding="utf-8") as handle:
            json.dump(graph_data, handle, indent=2)

    def _load_graph(self) -> None:
        if self.graph is None:
            return
        try:
            with open(GRAPH_STORE_PATH, "r", encoding="utf-8") as handle:
                graph_data = json.load(handle)
            self.graph = nx.node_link_graph(graph_data, directed=True)
        except Exception:
            logger.exception("graph_store.load_failed", extra={"event": "graph_store.load_failed"})


def initialize_graph_store() -> Optional[GraphStore]:
    try:
        return GraphStore()
    except Exception:
        logger.exception("graph_store.initialization_failed", extra={"event": "graph_store.initialization_failed"})
        return None

