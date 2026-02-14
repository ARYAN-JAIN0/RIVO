"""Vector memory store with graceful degradation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


BASE_DIR = Path(__file__).resolve().parents[1]
CHROMA_DB_PATH = BASE_DIR / "memory" / "chroma_db"


class VectorStore:
    def __init__(self) -> None:
        if not CHROMADB_AVAILABLE:
            self.client = None
            self.collections = {}
            logger.info("vector_store.disabled_missing_dependency", extra={"event": "vector_store.disabled_missing_dependency"})
            return

        try:
            CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=str(CHROMA_DB_PATH),
                settings=Settings(anonymized_telemetry=False),
            )
            self.collections = {
                "sdr_emails": self.client.get_or_create_collection("sdr_emails"),
                "sales_notes": self.client.get_or_create_collection("sales_notes"),
                "negotiations": self.client.get_or_create_collection("negotiations"),
                "dunning_messages": self.client.get_or_create_collection("dunning_messages"),
            }
            logger.info("vector_store.initialized", extra={"event": "vector_store.initialized"})
        except Exception:
            self.client = None
            self.collections = {}
            logger.warning("vector_store.disabled_runtime_error", extra={"event": "vector_store.disabled_runtime_error"})

    def add_sdr_email(self, lead_id: int, email_text: str, metadata: Dict) -> None:
        if not self.client:
            return
        self.collections["sdr_emails"].add(documents=[email_text], ids=[f"lead_{lead_id}"], metadatas=[metadata])

    def add_sales_note(self, deal_id: int, notes: str, metadata: Dict) -> None:
        if not self.client:
            return
        self.collections["sales_notes"].add(documents=[notes], ids=[f"deal_{deal_id}"], metadatas=[metadata])

    def add_negotiation(self, contract_id: int, objections: str, solutions: str, metadata: Dict) -> None:
        if not self.client:
            return
        combined = f"Objections: {objections}\n\nSolutions: {solutions}"
        self.collections["negotiations"].add(documents=[combined], ids=[f"contract_{contract_id}"], metadatas=[metadata])

    def add_dunning_message(self, invoice_id: int, message: str, metadata: Dict) -> None:
        if not self.client:
            return
        self.collections["dunning_messages"].add(documents=[message], ids=[f"invoice_{invoice_id}"], metadatas=[metadata])

    def search_similar_sdr_emails(self, query: str, n_results: int = 3) -> List[Dict]:
        if not self.client:
            return []
        results = self.collections["sdr_emails"].query(query_texts=[query], n_results=n_results)
        return self._format_results(results)

    def search_similar_negotiations(self, query: str, n_results: int = 3) -> List[Dict]:
        if not self.client:
            return []
        results = self.collections["negotiations"].query(query_texts=[query], n_results=n_results)
        return self._format_results(results)

    def get_customer_history(self, lead_id: int) -> Dict:
        if not self.client:
            return {}

        history = {"sdr_emails": [], "sales_notes": [], "negotiations": [], "dunning_messages": []}
        for collection_name, collection in self.collections.items():
            try:
                results = collection.get(where={"lead_id": lead_id})
                if results and results.get("documents"):
                    history[collection_name] = results["documents"]
            except Exception:
                continue
        return history

    @staticmethod
    def _format_results(results) -> List[Dict]:
        if not results or not results.get("documents"):
            return []

        formatted: List[Dict] = []
        for idx in range(len(results["documents"][0])):
            formatted.append(
                {
                    "text": results["documents"][0][idx],
                    "metadata": results["metadatas"][0][idx] if results.get("metadatas") else {},
                    "distance": results["distances"][0][idx] if results.get("distances") else None,
                }
            )
        return formatted


def initialize_vector_store() -> Optional[VectorStore]:
    try:
        return VectorStore()
    except Exception:
        logger.exception("vector_store.initialization_failed", extra={"event": "vector_store.initialization_failed"})
        return None
