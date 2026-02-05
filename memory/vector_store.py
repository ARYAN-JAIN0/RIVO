# ChromaDB

"""
Vector Store - ChromaDB for conversation embeddings

PHASE-3 EXTENSION: Read-only memory layer for agents.
Purpose: Store and retrieve conversation context, past interactions, objections, etc.

BACKWARD COMPATIBILITY:
- Never modifies CSV files
- Pure read operation for context enrichment
- Agents work WITHOUT vector store if unavailable
"""

import os
from pathlib import Path
from typing import List, Dict, Optional

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("⚠️  ChromaDB not installed. Vector store disabled.")
    print("   Install with: pip install chromadb")


# Configuration
BASE_DIR = Path(__file__).resolve().parents[1]
CHROMA_DB_PATH = BASE_DIR / "memory" / "chroma_db"


class VectorStore:
    """
    Vector store for semantic search over conversations and interactions.
    
    Collections:
    - sdr_emails: All SDR email drafts
    - sales_notes: Sales qualification notes
    - negotiations: Objection handling strategies
    - dunning_messages: Payment reminder emails
    """
    
    def __init__(self):
        if not CHROMADB_AVAILABLE:
            self.client = None
            self.collections = {}
            return
        
        # Create directory if doesn't exist
        CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DB_PATH),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collections
        self.collections = {
            "sdr_emails": self.client.get_or_create_collection("sdr_emails"),
            "sales_notes": self.client.get_or_create_collection("sales_notes"),
            "negotiations": self.client.get_or_create_collection("negotiations"),
            "dunning_messages": self.client.get_or_create_collection("dunning_messages")
        }
        
        print("✅ Vector Store initialized")
    
    def add_sdr_email(self, lead_id: int, email_text: str, metadata: Dict):
        """Store SDR email draft for future reference."""
        if not self.client:
            return
        
        self.collections["sdr_emails"].add(
            documents=[email_text],
            ids=[f"lead_{lead_id}"],
            metadatas=[metadata]
        )
    
    def add_sales_note(self, deal_id: int, notes: str, metadata: Dict):
        """Store sales qualification notes."""
        if not self.client:
            return
        
        self.collections["sales_notes"].add(
            documents=[notes],
            ids=[f"deal_{deal_id}"],
            metadatas=[metadata]
        )
    
    def add_negotiation(self, contract_id: int, objections: str, solutions: str, metadata: Dict):
        """Store negotiation strategies."""
        if not self.client:
            return
        
        combined_text = f"Objections: {objections}\n\nSolutions: {solutions}"
        
        self.collections["negotiations"].add(
            documents=[combined_text],
            ids=[f"contract_{contract_id}"],
            metadatas=[metadata]
        )
    
    def add_dunning_message(self, invoice_id: int, message: str, metadata: Dict):
        """Store dunning email drafts."""
        if not self.client:
            return
        
        self.collections["dunning_messages"].add(
            documents=[message],
            ids=[f"invoice_{invoice_id}"],
            metadatas=[metadata]
        )
    
    def search_similar_sdr_emails(self, query: str, n_results: int = 3) -> List[Dict]:
        """Find similar SDR emails for inspiration."""
        if not self.client:
            return []
        
        results = self.collections["sdr_emails"].query(
            query_texts=[query],
            n_results=n_results
        )
        
        return self._format_results(results)
    
    def search_similar_negotiations(self, query: str, n_results: int = 3) -> List[Dict]:
        """Find similar objection handling strategies."""
        if not self.client:
            return []
        
        results = self.collections["negotiations"].query(
            query_texts=[query],
            n_results=n_results
        )
        
        return self._format_results(results)
    
    def get_customer_history(self, lead_id: int) -> Dict:
        """
        Retrieve all interactions with a specific customer.
        Useful for context before next touchpoint.
        """
        if not self.client:
            return {}
        
        history = {
            "sdr_emails": [],
            "sales_notes": [],
            "negotiations": [],
            "dunning_messages": []
        }
        
        # Search each collection for this lead_id
        for collection_name, collection in self.collections.items():
            try:
                results = collection.get(
                    where={"lead_id": lead_id}
                )
                if results and results['documents']:
                    history[collection_name] = results['documents']
            except:
                pass  # Collection might be empty
        
        return history
    
    def _format_results(self, results) -> List[Dict]:
        """Format ChromaDB results into clean dict."""
        if not results or not results['documents']:
            return []
        
        formatted = []
        for i in range(len(results['documents'][0])):
            formatted.append({
                "text": results['documents'][0][i],
                "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                "distance": results['distances'][0][i] if results['distances'] else None
            })
        
        return formatted


def initialize_vector_store() -> Optional[VectorStore]:
    """
    Initialize vector store.
    Gracefully degrades if ChromaDB unavailable.
    """
    try:
        return VectorStore()
    except Exception as e:
        print(f"⚠️  Vector store initialization failed: {e}")
        print("   Agents will continue without semantic search capability.")
        return None


# Example usage
if __name__ == "__main__":
    vs = initialize_vector_store()
    
    if vs and vs.client:
        # Test storage
        vs.add_sdr_email(
            lead_id=999,
            email_text="Hi there, I noticed your company is hiring engineers...",
            metadata={"score": 85, "industry": "SaaS", "approved": True}
        )
        
        # Test retrieval
        similar = vs.search_similar_sdr_emails("hiring engineers", n_results=1)
        print(f"\n🔍 Similar emails found: {len(similar)}")
        if similar:
            print(f"   Example: {similar[0]['text'][:60]}...")
    else:
        print("\n⚠️  Vector store not available for testing")