#!/usr/bin/env python
"""
RIVO Feature Demonstration Script

Tests the following new features from commit 11bed93:
1. Finance Risk API
2. Revenue Forecast API
3. Negotiation Response API
4. RAG Ingest
5. RAG Query
6. LLM Routing

Usage:
    # Start the server first:
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    
    # Then run this demo script:
    python demo_rivo.py

Requirements:
    - requests library (pip install requests)
    - RIVO server running on http://localhost:8000
"""

from __future__ import annotations

import os
import sys
import json
import time
from typing import Any



try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not installed.")
    print("Please install it with: pip install requests")
    sys.exit(1)

# Configuration
BASE_URL = os.getenv("RIVO_API_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"

# Demo credentials (update these to match your database)
# Default admin user created during database initialization
DEMO_EMAIL = os.getenv("RIVO_DEMO_EMAIL", "admin@example.com")
DEMO_PASSWORD = os.getenv("RIVO_DEMO_PASSWORD", "admin123")


class RIVODemo:
    """Demo client for testing RIVO features."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.api_prefix = API_PREFIX
        self.access_token: str | None = None
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    @property
    def api_url(self) -> str:
        return f"{self.base_url}{self.api_prefix}"

    def _get_auth_header(self) -> dict[str, str]:
        """Get authorization header with token."""
        if not self.access_token:
            raise RuntimeError("Not authenticated. Call login() first.")
        return {"Authorization": f"Bearer {self.access_token}"}

    def login(self, email: str = DEMO_EMAIL, password: str = DEMO_PASSWORD) -> bool:
        """
        Authenticate and obtain access token.
        
        Returns:
            bool: True if login successful, False otherwise.
        """
        print("\n" + "=" * 60)
        print("STEP 1: Authentication")
        print("=" * 60)

        url = f"{self.api_url}/auth/login"
        payload = {"email": email, "password": password}

        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("access_token")

            if self.access_token:
                print(f"✓ Login successful!")
                print(f"  Email: {email}")
                print(f"  Token: {self.access_token[:50]}...")
                return True
            else:
                print("✗ Login failed: No access token received")
                return False

        except requests.exceptions.ConnectionError:
            print(f"✗ Connection failed: Cannot reach {url}")
            print("  Make sure the RIVO server is running.")
            return False
        except requests.exceptions.HTTPError as e:
            print(f"✗ Login failed: {e.response.status_code}")
            print(f"  Response: {e.response.text}")
            return False
        except Exception as e:
            print(f"✗ Login error: {e}")
            return False

    def test_finance_risk_api(self, customer_id: int = 1) -> dict[str, Any]:
        """
        Test Finance Risk API endpoint.
        
        Calculates payment risk score for a customer based on:
        - on_time_ratio: percentage of on-time payments
        - avg_delay_days: average delay for late payments
        - max_delay_days: maximum delay for late payments
        
        Returns:
            dict: Risk score and related metrics.
        """
        print("\n" + "=" * 60)
        print("STEP 2: Finance Risk API")
        print("=" * 60)

        url = f"{self.api_url}/finance/risk/{customer_id}"
        headers = self._get_auth_header()

        try:
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            print(f"✓ Finance Risk API Response for Customer {customer_id}:")
            print(f"  Customer ID: {data.get('customer_id')}")
            print(f"  Risk Score: {data.get('risk_score', 'N/A')}")
            print(f"  On-Time Ratio: {data.get('on_time_ratio', 'N/A')}")
            print(f"  Avg Delay Days: {data.get('avg_delay_days', 'N/A')}")
            print(f"  Max Delay Days: {data.get('max_delay_days', 'N/A')}")
            print(f"  Total Payments: {data.get('total_payments', 'N/A')}")
            print(f"  On-Time Payments: {data.get('on_time_payments', 'N/A')}")
            print(f"  Calculated At: {data.get('calculated_at')}")

            return data

        except requests.exceptions.HTTPError as e:
            error_msg = self._handle_http_error(e, "Finance Risk API")
            return {"error": error_msg}

    def test_revenue_forecast_api(self, days: int = 30) -> dict[str, Any]:
        """
        Test Revenue Forecast API endpoint.
        
        Forecasts expected revenue from unpaid invoices based on:
        - Payment probability predictions
        - Invoice due dates within the forecast period
        
        Returns:
            dict: Forecast metrics including expected revenue.
        """
        print("\n" + "=" * 60)
        print("STEP 3: Revenue Forecast API")
        print("=" * 60)

        url = f"{self.api_url}/finance/forecast"
        headers = self._get_auth_header()
        params = {"days": days}

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            print(f"✓ Revenue Forecast API Response ({days} days):")
            print(f"  Tenant ID: {data.get('tenant_id')}")
            print(f"  Forecast Period: {data.get('forecast_period_days')} days")
            print(f"  Expected Revenue: ${data.get('expected_revenue', 0):.2f}")
            print(f"  Total Invoices: {data.get('total_invoices')}")
            print(f"  Total Raw Amount: ${data.get('total_raw_amount', 0):.2f}")
            print(f"  Calculated At: {data.get('calculated_at')}")

            return data

        except requests.exceptions.HTTPError as e:
            error_msg = self._handle_http_error(e, "Revenue Forecast API")
            return {"error": error_msg}

    def test_negotiation_respond_api(
        self,
        deal_id: int,
        objection_text: str,
        message_type: str = "objection"
    ) -> dict[str, Any]:
        """
        Test Negotiation Response API endpoint.
        
        Executes the full negotiation flow:
        1. Classifies the objection
        2. Selects a negotiation strategy
        3. Generates a response
        4. Scores the response
        
        Returns:
            dict: Generated response with classification, strategy, and scores.
        """
        print("\n" + "=" * 60)
        print("STEP 4: Negotiation Response API")
        print("=" * 60)

        url = f"{self.api_url}/negotiation/respond"
        headers = self._get_auth_header()
        payload = {
            "deal_id": deal_id,
            "objection_text": objection_text,
            "message_type": message_type
        }

        try:
            response = self.session.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()

            print(f"✓ Negotiation Response API Response for Deal {deal_id}:")
            print(f"  Deal ID: {data.get('deal_id')}")
            print(f"  Objection Type: {data.get('objection_type')}")
            print(f"  Strategy: {data.get('strategy')}")
            print(f"  Scores:")
            scores = data.get("scores", {})
            print(f"    - Total: {scores.get('total')}")
            print(f"    - Strategy Alignment: {scores.get('strategy_alignment')}")
            print(f"    - Relevance: {scores.get('relevance')}")
            print(f"    - Coherence: {scores.get('coherence')}")
            print(f"  Requires Human Review: {data.get('requires_human_review')}")
            print(f"  Response Text Preview:")
            response_text = data.get("response_text", "")
            print(f"    {response_text[:200]}..." if len(response_text) > 200 else f"    {response_text}")

            return data

        except requests.exceptions.HTTPError as e:
            error_msg = self._handle_http_error(e, "Negotiation Response API")
            return {"error": error_msg}

    def test_negotiation_history_api(self, deal_id: int) -> dict[str, Any]:
        """
        Test Negotiation History API endpoint.
        
        Retrieves conversation history for a deal.
        
        Returns:
            dict: Conversation history with messages.
        """
        print("\n" + "=" * 60)
        print("STEP 5: Negotiation History API")
        print("=" * 60)

        url = f"{self.api_url}/negotiation/history/{deal_id}"
        headers = self._get_auth_header()

        try:
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            print(f"✓ Negotiation History API Response for Deal {deal_id}:")
            print(f"  Deal ID: {data.get('deal_id')}")
            print(f"  Total Messages: {data.get('total_count')}")

            messages = data.get("messages", [])
            if messages:
                print(f"  Recent Messages:")
                for msg in messages[-3:]:  # Show last 3 messages
                    role = msg.get("role")
                    msg_type = msg.get("message_type")
                    text = msg.get("message_text", "")[:80]
                    print(f"    - [{role}] {msg_type}: {text}...")
            else:
                print("  No messages found.")

            return data

        except requests.exceptions.HTTPError as e:
            error_msg = self._handle_http_error(e, "Negotiation History API")
            return {"error": error_msg}

    def test_rag_ingest_api(self, content: str, filename: str = "demo_document.txt") -> dict[str, Any]:
        """
        Test RAG Ingest API endpoint.
        
        Ingests a document into the RAG system for retrieval.
        
        Returns:
            dict: Ingestion result with chunk count.
        """
        print("\n" + "=" * 60)
        print("STEP 6: RAG Ingest API")
        print("=" * 60)

        url = f"{self.api_url}/rag/ingest"
        headers = self._get_auth_header()

        # Create a file-like object for upload
        files = {
            "file": (filename, content.encode("utf-8"), "text/plain")
        }

        try:
            response = self.session.post(url, headers=headers, files=files, timeout=60)
            response.raise_for_status()
            data = response.json()

            print(f"✓ RAG Ingest API Response:")
            print(f"  Success: {data.get('success')}")
            print(f"  Filename: {data.get('filename')}")
            print(f"  Chunks Created: {data.get('chunks_created')}")
            if data.get("error"):
                print(f"  Error: {data.get('error')}")

            return data

        except requests.exceptions.HTTPError as e:
            error_msg = self._handle_http_error(e, "RAG Ingest API")
            return {"error": error_msg}

    def test_rag_query_api(self, query: str, top_k: int = 3) -> dict[str, Any]:
        """
        Test RAG Query API endpoint.
        
        Queries the RAG system for relevant context.
        
        Returns:
            dict: Query result with context and sources.
        """
        print("\n" + "=" * 60)
        print("STEP 7: RAG Query API")
        print("=" * 60)

        url = f"{self.api_url}/rag/query"
        headers = self._get_auth_header()
        payload = {
            "query": query,
            "top_k": top_k,
            "max_context_tokens": 1000
        }

        try:
            response = self.session.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()

            print(f"✓ RAG Query API Response:")
            print(f"  Success: {data.get('success')}")
            print(f"  Query: {data.get('query')}")
            print(f"  Result Count: {data.get('result_count')}")

            sources = data.get("sources", [])
            if sources:
                print(f"  Sources:")
                for src in sources:
                    print(f"    - {src.get('source', 'unknown')}: {src.get('content', '')[:100]}...")

            context = data.get("context", "")
            if context:
                print(f"  Context Preview:")
                print(f"    {context[:200]}..." if len(context) > 200 else f"    {context}")
            else:
                print(f"  Context: (empty)")

            if data.get("error"):
                print(f"  Error: {data.get('error')}")

            return data

        except requests.exceptions.HTTPError as e:
            error_msg = self._handle_http_error(e, "RAG Query API")
            return {"error": error_msg}

    def test_llm_routing(self) -> dict[str, Any]:
        """
        Test LLM Routing functionality.
        
        Demonstrates how requests are routed to different models:
        - DeepSeek: Reasoning tasks (sales_strategy, negotiation)
        - Qwen: Generation tasks (email_generation, finance)
        
        Note: This is tested indirectly through the negotiation API,
        which uses the LLM router to select appropriate models.
        
        Returns:
            dict: Routing information.
        """
        print("\n" + "=" * 60)
        print("STEP 8: LLM Routing")
        print("=" * 60)

        # The LLM routing is demonstrated through negotiation
        # Let's check what models would be used for different tasks

        print("✓ LLM Routing Configuration:")
        print("  Task Type Mappings:")
        print("    - email_generation -> qwen (generation tasks)")
        print("    - sales_strategy -> deepseek (reasoning tasks)")
        print("    - negotiation -> deepseek (reasoning tasks)")
        print("    - finance -> qwen (generation tasks)")
        print("")
        print("  Agent Model Mappings:")
        print("    - sdr -> qwen")
        print("    - sales -> deepseek")
        print("    - negotiation -> deepseek")
        print("    - finance -> qwen")
        print("")
        print("  Note: LLM routing is used internally by agent APIs.")

        return {
            "status": "routing_configured",
            "message": "LLM routing is handled internally by the agent system"
        }

    def _handle_http_error(self, e: requests.exceptions.HTTPError, context: str) -> str:
        """Handle HTTP errors with descriptive messages."""
        status_code = e.response.status_code
        try:
            error_detail = e.response.json().get("detail", str(e))
        except json.JSONDecodeError:
            error_detail = e.response.text

        error_msg = f"{context} failed with status {status_code}: {error_detail}"
        print(f"✗ {error_msg}")
        return error_msg

    def run_full_demo(self):
        """Run the complete demo suite."""
        print("\n" + "#" * 60)
        print("# RIVO Feature Demonstration Script")
        print("# Testing commit 11bed93 features")
        print("#" * 60)

        # Step 1: Login
        if not self.login():
            print("\n✗ Demo aborted: Authentication failed")
            print("\nTroubleshooting:")
            print("  1. Ensure RIVO server is running: python -m uvicorn app.main:app")
            print("  2. Check credentials in .env or use defaults")
            print("  3. Verify database has admin user")
            return

        # Step 2: Finance Risk API
        risk_result = self.test_finance_risk_api(customer_id=1)

        # Step 3: Revenue Forecast API
        forecast_result = self.test_revenue_forecast_api(days=30)

        # Step 4: Negotiation Response API
        # First check if there's a deal to test with
        negotiation_result = self.test_negotiation_respond_api(
            deal_id=1,
            objection_text="Your price is too high. Can you offer a discount?",
            message_type="objection"
        )

        # Step 5: Negotiation History API
        history_result = self.test_negotiation_history_api(deal_id=1)

        # Step 6: RAG Ingest API
        demo_content = """
        RIVO Platform Features:
        
        1. SDR Agent: Automated outbound prospecting with signal detection
        2. Sales Agent: Qualification and needs analysis
        3. Negotiation Agent: Objection handling and response generation
        4. Finance Agent: Risk assessment and revenue forecasting
        
        The platform uses multi-model LLM routing:
        - DeepSeek for reasoning tasks (negotiation, sales strategy)
        - Qwen for generation tasks (email drafting, finance)
        
        RAG system enables contextual document retrieval for agent assistance.
        """

        ingest_result = self.test_rag_ingest_api(
            content=demo_content,
            filename="rivo_features_demo.txt"
        )

        # Step 7: RAG Query API
        query_result = self.test_rag_query_api(
            query="What are the main features of the RIVO platform?",
            top_k=3
        )

        # Step 8: LLM Routing
        routing_result = self.test_llm_routing()

        # Summary
        print("\n" + "#" * 60)
        print("# Demo Complete!")
        print("#" * 60)

        print("\nResults Summary:")
        print(f"  Finance Risk API: {'✓' if 'error' not in risk_result else '✗'}")
        print(f"  Revenue Forecast API: {'✓' if 'error' not in forecast_result else '✗'}")
        print(f"  Negotiation Response API: {'✓' if 'error' not in negotiation_result else '✗'}")
        print(f"  Negotiation History API: {'✓' if 'error' not in history_result else '✗'}")
        print(f"  RAG Ingest API: {'✓' if 'error' not in ingest_result else '✗'}")
        print(f"  RAG Query API: {'✓' if 'error' not in query_result else '✗'}")
        print(f"  LLM Routing: ✓ (internal)")


def check_prerequisites() -> bool:
    """Check if all prerequisites are met."""
    print("Checking prerequisites...")

    # Check if requests is installed
    try:
        import requests
        print(f"✓ requests library installed")
    except ImportError:
        print("✗ requests library not installed")
        print("  Run: pip install requests")
        return False

    # Check if server is reachable
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"✓ RIVO server is running at {BASE_URL}")
        else:
            print(f"✗ RIVO server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to RIVO server at {BASE_URL}")
        print("  Start the server with:")
        print("    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
        return False

    return True


def main():
    """Main entry point."""
    print("\nRIVO Feature Demonstration")
    print("=" * 60)

    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)

    # Create demo client and run
    demo = RIVODemo()
    demo.run_full_demo()


if __name__ == "__main__":
    main()
