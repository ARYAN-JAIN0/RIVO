"""Retriever abstraction for RAG flows."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.rag.embeddings.ollama_embedder import get_embedder
from app.rag.vector_store.pgvector_store import PGVectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedDocument:
    """A retrieved document from the vector store."""
    document_id: str
    content: str
    score: float
    metadata: dict


class Retriever:
    """Embedding + vector-store retrieval coordinator.

    Coordinates embedding generation and vector similarity search
    with tenant isolation.
    """

    def __init__(
        self,
        embedding_provider=None,
        vector_store=None,
    ) -> None:
        """Initialize the retriever.

        Args:
            embedding_provider: Custom embedding provider (optional).
            vector_store: Custom vector store (optional).
        """
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store or PGVectorStore()

    @property
    def embedding_provider(self):
        """Get or create the embedding provider."""
        if self._embedding_provider is None:
            self._embedding_provider = get_embedder()
        return self._embedding_provider

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        tenant_id: int = 1,
    ) -> list[RetrievedDocument]:
        """Retrieve relevant documents for a query.

        Args:
            query: The search query.
            top_k: Number of results to return.
            tenant_id: The tenant ID for isolation.

        Returns:
            List of retrieved documents with scores.
        """
        if not query or not query.strip():
            logger.warning(
                "rag.retriever.empty_query",
                extra={"event": "rag.retriever.empty_query", "tenant_id": tenant_id},
            )
            return []

        # Generate embedding for the query
        embedding_result = self.embedding_provider.embed(query)
        query_embedding = embedding_result.vector

        if not query_embedding:
            logger.warning(
                "rag.retriever.empty_embedding",
                extra={
                    "event": "rag.retriever.empty_embedding",
                    "query": query[:100],
                    "tenant_id": tenant_id,
                },
            )
            # Fallback to empty result
            return []

        # Search vector store
        try:
            results = self._vector_store.similarity_search(
                query_embedding=query_embedding,
                top_k=top_k,
                tenant_id=tenant_id,
            )

            documents = []
            for doc, score in results:
                documents.append(
                    RetrievedDocument(
                        document_id=doc.doc_id,
                        content=doc.text,
                        score=score,
                        metadata=doc.metadata,
                    )
                )

            logger.info(
                "rag.retriever.retrieved",
                extra={
                    "event": "rag.retriever.retrieved",
                    "query": query[:100],
                    "tenant_id": tenant_id,
                    "result_count": len(documents),
                },
            )

            return documents

        except Exception as exc:
            logger.error(
                "rag.retriever.error",
                extra={
                    "event": "rag.retriever.error",
                    "error": str(exc),
                    "tenant_id": tenant_id,
                },
            )
            return []


def get_retriever() -> Retriever:
    """Get the default retriever instance.

    Returns:
        Configured Retriever instance.
    """
    return Retriever()
