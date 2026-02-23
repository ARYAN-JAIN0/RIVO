#!/usr/bin/env python
"""
RIVO Pipeline Demo Script

This script:
1. Seeds test lead data
2. Runs the full 4-agent pipeline (SDR → Sales → Negotiation → Finance)
3. Shows the results at each stage

Usage:
    python run_pipeline_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.enums import LeadStatus
from app.database.db import get_db_session
from app.database.models import Lead, Deal, Contract, Invoice, Tenant
from app.orchestrator import RevoOrchestrator
from app.core.startup import bootstrap


def check_prerequisites() -> bool:
    """Check if Ollama and database are ready."""
    import requests
    
    print("=" * 60)
    print("RIVO Pipeline Demo - Prerequisites Check")
    print("=" * 60)
    
    # Check Ollama
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]
            print(f"[OK] Ollama is running with models: {model_names}")
        else:
            print("[FAIL] Ollama returned unexpected status")
            return False
    except Exception as e:
        print(f"[FAIL] Ollama not accessible: {e}")
        return False
    
    # Check database
    try:
        with get_db_session() as session:
            lead_count = session.query(Lead).count()
            print(f"[OK] Database connected. Current leads: {lead_count}")
    except Exception as e:
        print(f"[FAIL] Database not accessible: {e}")
        return False
    
    print()
    return True


def seed_test_leads() -> int:
    """Seed test leads into the database."""
    print("=" * 60)
    print("Seeding Test Leads")
    print("=" * 60)
    
    test_leads = [
        {
            "name": "Sarah Chen",
            "email": "sarah.chen@techstartup.io",
            "role": "VP of Engineering",
            "company": "TechStartup.io",
            "website": "https://techstartup.io",
            "industry": "Software",
            "company_size": "51-200",
            "location": "San Francisco, CA",
            "verified_insight": "Recently raised Series B funding. Looking to scale engineering team.",
        },
        {
            "name": "Michael Rodriguez",
            "email": "mrodriguez@enterprise-corp.com",
            "role": "CTO",
            "company": "Enterprise Corp",
            "website": "https://enterprise-corp.com",
            "industry": "Enterprise Software",
            "company_size": "1000-5000",
            "location": "Austin, TX",
            "verified_insight": "Digital transformation initiative. Evaluating automation tools.",
        },
        {
            "name": "Emily Watson",
            "email": "emily.watson@innovate-labs.com",
            "role": "Head of Operations",
            "company": "Innovate Labs",
            "website": "https://innovate-labs.com",
            "industry": "Technology",
            "company_size": "201-500",
            "location": "New York, NY",
            "verified_insight": "Growing rapidly. Needs sales automation for scaling.",
        },
    ]
    
    inserted = 0
    with get_db_session() as session:
        # Ensure tenant exists
        tenant = session.query(Tenant).filter(Tenant.id == 1).first()
        if not tenant:
            tenant = Tenant(id=1, name="Default Tenant")
            session.add(tenant)
            session.commit()
        
        for lead_data in test_leads:
            # Check if lead already exists
            existing = session.query(Lead).filter(
                Lead.email == lead_data["email"]
            ).first()
            
            if existing:
                print(f"  Lead already exists: {lead_data['name']} ({lead_data['company']})")
                continue
            
            lead = Lead(
                name=lead_data["name"],
                email=lead_data["email"],
                role=lead_data.get("role"),
                company=lead_data.get("company"),
                website=lead_data.get("website"),
                industry=lead_data.get("industry"),
                company_size=lead_data.get("company_size"),
                location=lead_data.get("location"),
                verified_insight=lead_data.get("verified_insight"),
                status=LeadStatus.NEW.value,
                tenant_id=1,
            )
            session.add(lead)
            inserted += 1
            print(f"  + Added: {lead_data['name']} ({lead_data['company']})")
        
        session.commit()
    
    print(f"\nSeeded {inserted} new leads.")
    return inserted


def show_system_state():
    """Show current state of all entities."""
    print("\n" + "=" * 60)
    print("Current System State")
    print("=" * 60)
    
    with get_db_session() as session:
        # Leads
        leads = session.query(Lead).all()
        print(f"\nLeads ({len(leads)}):")
        for lead in leads:
            print(f"  [{lead.status}] {lead.name} - {lead.company} ({lead.email})")
        
        # Deals
        deals = session.query(Deal).all()
        print(f"\nDeals ({len(deals)}):")
        for deal in deals:
            print(f"  [{deal.stage}] {deal.company} - ACV: ${deal.acv or 0:,}")
        
        # Contracts
        contracts = session.query(Contract).all()
        print(f"\nContracts ({len(contracts)}):")
        for contract in contracts:
            print(f"  [{contract.status}] Deal #{contract.deal_id} - Value: ${contract.contract_value or 0:,}")
        
        # Invoices
        invoices = session.query(Invoice).all()
        print(f"\nInvoices ({len(invoices)}):")
        for invoice in invoices:
            print(f"  [{invoice.status}] Contract #{invoice.contract_id} - Amount: ${invoice.amount or 0:,}")


def run_pipeline():
    """Run the full 4-agent pipeline."""
    print("\n" + "=" * 60)
    print("Running Full Pipeline: SDR -> Sales -> Negotiation -> Finance")
    print("=" * 60)
    
    # Initialize
    bootstrap()
    orchestrator = RevoOrchestrator()
    
    # Run each agent and show results
    agents = ["sdr", "sales", "negotiation", "finance"]
    
    for agent in agents:
        print(f"\n--- Running {agent.upper()} Agent ---")
        try:
            result = orchestrator.run_single_agent(agent)
            print(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Show state after each agent
        show_system_state()
    
    print("\n" + "=" * 60)
    print("Pipeline Complete!")
    print("=" * 60)


def main():
    print("\n" + "=" * 60)
    print("RIVO 4-Agent Pipeline Demo")
    print("=" * 60)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\nPrerequisites not met. Please ensure Ollama is running.")
        sys.exit(1)
    
    # Seed test data
    seed_test_leads()
    
    # Show initial state
    show_system_state()
    
    # Run pipeline
    run_pipeline()


if __name__ == "__main__":
    main()
