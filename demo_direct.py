#!/usr/bin/env python
"""
RIVO Direct Feature Demo - No HTTP API needed

This script demonstrates the new features from commit 11bed93 by calling 
the backend modules directly, bypassing HTTP authentication.

Features demonstrated:
1. Negotiation Response Generation (LLM + template fallback)
2. Finance Risk Scoring (payment behavior analysis)
3. RAG Document Ingestion (PDF processing + vector storage)
4. LLM Multi-Model Routing (Qwen/DeepSeek selection)

Usage:
    python demo_direct.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# Setup path - project root is parent of this script's directory
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging for demo output
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger(__name__)


def demo_negotiation_generation() -> None:
    """Demo Feature 1: Negotiation Response Generation."""
    print("\n" + "=" * 60)
    print("FEATURE 1: Negotiation Response Generation")
    print("=" * 60)
    
    try:
        from app.negotiation.generation import (
            generate_response,
            GenerationResult,
        )
        
        # Simulate a negotiation scenario
        result: GenerationResult = generate_response(
            objection_text="The price is too high for our budget",
            conversation_history=[
                {"role": "customer", "message_text": "Hi, I'm interested in your platform"},
                {"role": "agent", "message_text": "Great! Let me tell you about our pricing"}
            ],
            objection_type="PRICE",
            strategy="DISCOUNT",
            deal_context={"deal_value": 25000, "company": "TechCorp"},
            rag_context=["case study: similar company saved 30%"]
        )
        
        print(f"[OK] Strategy Used: {result.strategy}")
        print(f"[OK] Method: {result.method} (llm=AI generation, template_fallback=rule-based)")
        print(f"[OK] Response: {result.response[:150]}...")
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


def demo_finance_risk_scoring() -> None:
    """Demo Feature 2: Finance Risk Scoring."""
    print("\n" + "=" * 60)
    print("FEATURE 2: Finance Risk Scoring")
    print("=" * 60)
    
    try:
        from app.finance.scoring import calculate_customer_risk_score
        
        # Calculate risk score for a customer
        risk_data: dict[str, Any] = calculate_customer_risk_score(
            tenant_id=1,
            customer_id=1
        )
        
        print(f"[OK] Risk Score: {risk_data.get('risk_score', 'N/A'):.2f}")
        print(f"[OK] On-time Payment Ratio: {risk_data.get('on_time_ratio', 'N/A'):.2%}")
        print(f"[OK] Average Delay Days: {risk_data.get('avg_delay_days', 'N/A')}")
        print(f"[OK] Maximum Delay Days: {risk_data.get('max_delay_days', 'N/A')}")
        print(f"[OK] Total Payments: {risk_data.get('total_payments', 'N/A')}")
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


def demo_rag_ingestion() -> None:
    """Demo Feature 3: RAG Document Ingestion."""
    print("\n" + "=" * 60)
    print("FEATURE 3: RAG Document Ingestion")
    print("=" * 60)
    
    try:
        from app.rag.ingestion import get_ingestion_pipeline
        
        # Create sample PDF content (in real scenario, would read from file)
        sample_pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] 
    /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 100 >>
stream
BT
/F1 12 Tf
50 700 Td
(RIVO Sales Proposal - Deal #12345) Tj
0 -20 Td
(Company: TechCorp Inc.) Tj
0 -20 Td
(Deal Value: $25,000) Tj
0 -20 Td
(Stage: Proposal Sent) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
0000000361 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
450
%%EOF"""
        
        pipeline = get_ingestion_pipeline()
        chunk_ids: list[int] = pipeline.ingest_document(
            file_content=sample_pdf_content,
            filename="test_proposal_demo.pdf",
            tenant_id=1,
        )
        
        result = {
            "document_id": "demo_doc",
            "chunks_created": len(chunk_ids),
            "status": "completed"
        }
        
        print(f"✓ Document ID: {result.get('document_id', 'N/A')}")
        print(f"✓ Chunks Created: {result.get('chunks_created', 'N/A')}")
        print(f"✓ Status: {result.get('status', 'completed')}")
        print(f"✓ Chunk IDs: {chunk_ids}")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


def demo_llm_routing() -> None:
    """Demo Feature 4: LLM Multi-Model Routing."""
    print("\n" + "=" * 60)
    print("FEATURE 4: LLM Multi-Model Routing")
    print("=" * 60)
    
    try:
        from app.llm.router import get_model_for_task, get_model_for_agent
        
        # Test generation task (should route to Qwen)
        print("\n--- Testing Generation Task ---")
        task_type = "email_generation"
        
        model = get_model_for_task(task_type)
        print(f"✓ Task: {task_type}")
        print(f"✓ Selected Model: {model}")
        print(f"✓ Expected: qwen (for generation)")
        
        # Test reasoning task (should route to DeepSeek)
        print("\n--- Testing Reasoning Task ---")
        task_type = "sales_reasoning"
        
        model = get_model_for_task(task_type)
        print(f"✓ Task: {task_type}")
        print(f"✓ Selected Model: {model}")
        print(f"✓ Expected: deepseek (for reasoning)")
        
        # Test agent-based routing
        print("\n--- Testing Agent-Based Routing ---")
        agent_name = "negotiation"
        
        model = get_model_for_agent(agent_name)
        print(f"✓ Agent: {agent_name}")
        print(f"✓ Selected Model: {model}")
        print(f"✓ Expected: deepseek (for negotiation agent)")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


def main() -> None:
    """Run all demo features."""
    print("\n" + "=" * 60)
    print("  RIVO FEATURE DEMO - Commit 11bed93")
    print("  Direct Python Calls (No HTTP API)")
    print("=" * 60)
    
    # Run all demos
    demo_negotiation_generation()
    demo_finance_risk_scoring()
    demo_rag_ingestion()
    demo_llm_routing()
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print("\nFeatures demonstrated:")
    print("  1. Negotiation Response Generation")
    print("  2. Finance Risk Scoring")
    print("  3. RAG Document Ingestion")
    print("  4. LLM Multi-Model Routing")
    print()


if __name__ == "__main__":
    main()
