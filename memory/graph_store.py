# NetworkX

"""
Graph Store - NetworkX for relationship mapping

PHASE-3 EXTENSION: Track relationships and progression through pipeline.
Purpose: Map lead → deal → contract → invoice relationships and identify patterns.

BACKWARD COMPATIBILITY:
- Never modifies CSV files
- Pure read operation for analytics
- Agents work WITHOUT graph store if unavailable
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    print("⚠️  NetworkX not installed. Graph store disabled.")
    print("   Install with: pip install networkx")


# Configuration
BASE_DIR = Path(__file__).resolve().parents[1]
GRAPH_STORE_PATH = BASE_DIR / "memory" / "graph_store.json"


class GraphStore:
    """
    Graph-based relationship store for tracking:
    - Lead → Deal → Contract → Invoice progression
    - Company → Multiple Contacts (organization chart)
    - Similar Companies (industry clusters)
    - Successful Patterns (what worked)
    """
    
    def __init__(self):
        if not NETWORKX_AVAILABLE:
            self.graph = None
            return
        
        self.graph = nx.DiGraph()  # Directed graph for pipeline flow
        
        # Try to load existing graph
        if GRAPH_STORE_PATH.exists():
            self._load_graph()
        
        print("✅ Graph Store initialized")
    
    def add_lead(self, lead_id: int, metadata: Dict):
        """Add lead node to graph."""
        if not self.graph:
            return
        
        self.graph.add_node(
            f"lead_{lead_id}",
            node_type="lead",
            **metadata
        )
    
    def add_deal(self, deal_id: int, lead_id: int, metadata: Dict):
        """Add deal node and link to lead."""
        if not self.graph:
            return
        
        deal_node = f"deal_{deal_id}"
        lead_node = f"lead_{lead_id}"
        
        self.graph.add_node(deal_node, node_type="deal", **metadata)
        self.graph.add_edge(lead_node, deal_node, relationship="converted_to")
    
    def add_contract(self, contract_id: int, deal_id: int, metadata: Dict):
        """Add contract node and link to deal."""
        if not self.graph:
            return
        
        contract_node = f"contract_{contract_id}"
        deal_node = f"deal_{deal_id}"
        
        self.graph.add_node(contract_node, node_type="contract", **metadata)
        self.graph.add_edge(deal_node, contract_node, relationship="progressed_to")
    
    def add_invoice(self, invoice_id: int, contract_id: int, metadata: Dict):
        """Add invoice node and link to contract."""
        if not self.graph:
            return
        
        invoice_node = f"invoice_{invoice_id}"
        contract_node = f"contract_{contract_id}"
        
        self.graph.add_node(invoice_node, node_type="invoice", **metadata)
        self.graph.add_edge(contract_node, invoice_node, relationship="invoiced")
    
    def add_company_relationship(self, company_name: str, lead_id: int):
        """Link multiple leads from same company."""
        if not self.graph:
            return
        
        company_node = f"company_{company_name.replace(' ', '_').lower()}"
        lead_node = f"lead_{lead_id}"
        
        if not self.graph.has_node(company_node):
            self.graph.add_node(company_node, node_type="company", name=company_name)
        
        self.graph.add_edge(company_node, lead_node, relationship="employee")
    
    def get_lead_journey(self, lead_id: int) -> List[Dict]:
        """
        Trace complete journey of a lead through the pipeline.
        Returns chronological list of stages.
        """
        if not self.graph:
            return []
        
        lead_node = f"lead_{lead_id}"
        if not self.graph.has_node(lead_node):
            return []
        
        journey = []
        
        # BFS traversal to find all connected nodes
        visited = set()
        queue = [lead_node]
        
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            
            visited.add(node)
            node_data = self.graph.nodes[node]
            
            journey.append({
                "node": node,
                "type": node_data.get("node_type"),
                "data": node_data
            })
            
            # Add outgoing edges (progression)
            for successor in self.graph.successors(node):
                if successor not in visited:
                    queue.append(successor)
        
        return journey
    
    def find_conversion_patterns(self, min_deal_value: int = 50000) -> Dict:
        """
        Analyze successful patterns: What characteristics lead to high-value deals?
        """
        if not self.graph:
            return {}
        
        patterns = {
            "successful_industries": {},
            "successful_roles": {},
            "avg_time_to_close": 0,
            "conversion_rate": 0
        }
        
        # Find all deals above threshold
        high_value_deals = [
            node for node, data in self.graph.nodes(data=True)
            if data.get("node_type") == "deal" 
            and data.get("deal_value", 0) >= min_deal_value
        ]
        
        # Trace back to original leads
        for deal_node in high_value_deals:
            predecessors = list(self.graph.predecessors(deal_node))
            if predecessors:
                lead_node = predecessors[0]  # Should be lead
                lead_data = self.graph.nodes[lead_node]
                
                # Count industry
                industry = lead_data.get("industry", "Unknown")
                patterns["successful_industries"][industry] = \
                    patterns["successful_industries"].get(industry, 0) + 1
                
                # Count role
                role = lead_data.get("role", "Unknown")
                patterns["successful_roles"][role] = \
                    patterns["successful_roles"].get(role, 0) + 1
        
        # Calculate conversion rate
        total_leads = sum(1 for n, d in self.graph.nodes(data=True) if d.get("node_type") == "lead")
        total_deals = sum(1 for n, d in self.graph.nodes(data=True) if d.get("node_type") == "deal")
        
        if total_leads > 0:
            patterns["conversion_rate"] = round(total_deals / total_leads * 100, 1)
        
        return patterns
    
    def get_company_contacts(self, company_name: str) -> List[int]:
        """Find all leads from a specific company."""
        if not self.graph:
            return []
        
        company_node = f"company_{company_name.replace(' ', '_').lower()}"
        if not self.graph.has_node(company_node):
            return []
        
        # Get all leads connected to this company
        lead_ids = []
        for successor in self.graph.successors(company_node):
            if successor.startswith("lead_"):
                lead_id = int(successor.split("_")[1])
                lead_ids.append(lead_id)
        
        return lead_ids
    
    def get_stats(self) -> Dict:
        """Get overall graph statistics."""
        if not self.graph:
            return {"error": "Graph not initialized"}
        
        node_counts = {}
        for node, data in self.graph.nodes(data=True):
            node_type = data.get("node_type", "unknown")
            node_counts[node_type] = node_counts.get(node_type, 0) + 1
        
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_counts": node_counts,
            "avg_connections": round(self.graph.number_of_edges() / max(self.graph.number_of_nodes(), 1), 2)
        }
    
    def save_graph(self):
        """Persist graph to disk."""
        if not self.graph:
            return
        
        # Create directory if needed
        GRAPH_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to JSON-serializable format
        graph_data = nx.node_link_data(self.graph)
        
        with open(GRAPH_STORE_PATH, 'w') as f:
            json.dump(graph_data, f, indent=2)
        
        print(f"💾 Graph saved to {GRAPH_STORE_PATH}")
    
    def _load_graph(self):
        """Load graph from disk."""
        try:
            with open(GRAPH_STORE_PATH, 'r') as f:
                graph_data = json.load(f)
            
            self.graph = nx.node_link_graph(graph_data, directed=True)
            print(f"📂 Graph loaded from {GRAPH_STORE_PATH}")
        
        except Exception as e:
            print(f"⚠️  Failed to load graph: {e}")


def initialize_graph_store() -> Optional[GraphStore]:
    """
    Initialize graph store.
    Gracefully degrades if NetworkX unavailable.
    """
    try:
        return GraphStore()
    except Exception as e:
        print(f"⚠️  Graph store initialization failed: {e}")
        print("   Agents will continue without relationship tracking.")
        return None


# Example usage
if __name__ == "__main__":
    gs = initialize_graph_store()
    
    if gs and gs.graph:
        # Test data
        gs.add_lead(1, {"name": "Alice", "company": "TechCorp", "industry": "SaaS", "role": "CTO"})
        gs.add_company_relationship("TechCorp", 1)
        
        gs.add_deal(10, 1, {"deal_value": 75000, "stage": "Won"})
        gs.add_contract(100, 10, {"value": 75000, "status": "Signed"})
        gs.add_invoice(1000, 100, {"amount": 75000, "status": "Paid"})
        
        # Test retrieval
        journey = gs.get_lead_journey(1)
        print(f"\n📊 Lead Journey: {len(journey)} stages")
        for stage in journey:
            print(f"   - {stage['type']}: {stage['node']}")
        
        stats = gs.get_stats()
        print(f"\n📈 Graph Stats: {stats}")
        
        gs.save_graph()
    else:
        print("\n⚠️  Graph store not available for testing")