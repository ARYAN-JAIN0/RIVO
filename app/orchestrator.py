"""
Central Orchestrator for Revo Multi-Agent System

CRITICAL: This orchestrator EXTENDS Phase-2 without modifying existing SDR logic.
It coordinates event-driven workflows across SDR → Sales → Negotiation → Finance agents.

BACKWARD COMPATIBILITY GUARANTEES:
- SDR Agent runs independently (existing behavior preserved)
- New agents trigger ONLY on state transitions from SDR completions
- Existing leads.csv schema unchanged
- All new data stored in separate CSV files
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Ensure project root is importable - FIXED FOR WINDOWS
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.sdr_agent import run_sdr_agent
from agents.sales_agent import run_sales_agent
from agents.negotiation_agent import run_negotiation_agent
from agents.finance_agent import run_finance_agent
from db.db_handler import fetch_leads_by_status
from memory.vector_store import initialize_vector_store
from memory.graph_store import initialize_graph_store


class RevoOrchestrator:
    """
    Event-driven orchestrator for multi-agent workflows.
    
    State Machine:
    1. SDR: New → Contacted (email approved)
    2. Sales: Contacted → Qualified → Proposal Sent → Deal Won
    3. Negotiation: Proposal Sent → Negotiating → Contract Signed
    4. Finance: Contract Signed → Invoice Sent → Paid / Overdue
    """
    
    def __init__(self):
        self.agents = {
            'sdr': run_sdr_agent,
            'sales': run_sales_agent,
            'negotiation': run_negotiation_agent,
            'finance': run_finance_agent
        }
        
        # Initialize memory layers (non-destructive)
        self.vector_store = initialize_vector_store()
        self.graph_store = initialize_graph_store()
        
        print("🧠 Revo Orchestrator Initialized")
        print(f"   Agents: {list(self.agents.keys())}")
        print(f"   Memory: Vector Store + Graph Store")
    
    def run_pipeline(self, agents_to_run: List[str] = None):
        """
        Execute agent pipeline in sequence.
        
        Args:
            agents_to_run: List of agent names, or None to run all
        
        SAFETY: Each agent is independent. If one fails, others continue.
        """
        if agents_to_run is None:
            agents_to_run = ['sdr', 'sales', 'negotiation', 'finance']
        
        print(f"\n{'='*60}")
        print(f"🚀 Starting Revo Pipeline: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        results = {}
        
        for agent_name in agents_to_run:
            if agent_name not in self.agents:
                print(f"⚠️  Unknown agent: {agent_name}")
                continue
            
            try:
                print(f"\n{'─'*60}")
                print(f"🤖 Running {agent_name.upper()} Agent...")
                print(f"{'─'*60}")
                
                agent_fn = self.agents[agent_name]
                agent_fn()
                
                results[agent_name] = "✅ Success"
                print(f"\n✅ {agent_name.upper()} Agent completed")
                
            except Exception as e:
                results[agent_name] = f"❌ Error: {str(e)}"
                print(f"\n❌ {agent_name.upper()} Agent failed: {e}")
                import traceback
                traceback.print_exc()
                # Continue to next agent (fault isolation)
        
        self._print_summary(results)
        
        return results
    
    def run_single_agent(self, agent_name: str):
        """Run a single agent on-demand."""
        return self.run_pipeline(agents_to_run=[agent_name])
    
    def get_system_health(self) -> Dict:
        """
        Return health metrics across all stages.
        
        BACKWARD COMPATIBLE: Only reads from CSVs, never writes.
        """
        try:
            # SDR Stage
            new_leads = fetch_leads_by_status("New")
            pending_reviews = fetch_leads_by_status("Pending")
            contacted = fetch_leads_by_status("Contacted")
            
            # Sales Stage (from new CSV)
            from db.db_handler import fetch_deals_by_status
            qualified = fetch_deals_by_status("Qualified")
            proposals = fetch_deals_by_status("Proposal Sent")
            
            # Negotiation Stage
            from db.db_handler import fetch_contracts_by_status
            negotiating = fetch_contracts_by_status("Negotiating")
            
            # Finance Stage
            from db.db_handler import fetch_invoices_by_status
            overdue = fetch_invoices_by_status("Overdue")
            
            return {
                "timestamp": datetime.now().isoformat(),
                "sdr": {
                    "new_leads": len(new_leads),
                    "pending_review": len(pending_reviews),
                    "contacted": len(contacted)
                },
                "sales": {
                    "qualified": len(qualified),
                    "proposals_sent": len(proposals)
                },
                "negotiation": {
                    "active_negotiations": len(negotiating)
                },
                "finance": {
                    "overdue_invoices": len(overdue)
                }
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _print_summary(self, results: Dict):
        """Print execution summary."""
        print(f"\n{'='*60}")
        print(f"📊 Pipeline Summary")
        print(f"{'='*60}")
        
        for agent, status in results.items():
            print(f"   {agent.upper()}: {status}")
        
        print(f"{'='*60}\n")


def main():
    """
    Main entry point for orchestrator.
    
    USAGE:
        python app/orchestrator.py              # Run all agents
        python app/orchestrator.py sdr          # Run only SDR
        python app/orchestrator.py sales        # Run only Sales
        python app/orchestrator.py health       # Check system health
    """
    orchestrator = RevoOrchestrator()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "health":
            health = orchestrator.get_system_health()
            print("\n🏥 System Health:")
            import json
            print(json.dumps(health, indent=2))
        
        elif command in orchestrator.agents:
            orchestrator.run_single_agent(command)
        
        else:
            print(f"❌ Unknown command: {command}")
            print(f"   Available: {list(orchestrator.agents.keys()) + ['health']}")
    
    else:
        # Run full pipeline
        orchestrator.run_pipeline()


if __name__ == "__main__":
    main()