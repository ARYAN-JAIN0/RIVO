"""PGVector store with PostgreSQL backend and in-memory fallback."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from math import sqrt
from typing import Any

from sqlalchemy import text

from app.database.db import get_db_session
from app.database.models import RagDocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """Document with embedding for vector similarity search."""
    doc_id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sqrt(sum(x * x for x in a))
    norm_b = sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class PGVectorStore:
    """Vector store using PostgreSQL with pgvector.

    Supports both real pgvector similarity search and fallback to
    recent chunks when vector search fails.
    """

    def __init__(self, session=None):
        """Initialize the vector store.

        Args:
            session: Optional database session. If not provided,
                    uses get_db_session() context manager.
        """
        self._session = session
        self._owns_session = session is None

    def _get_session(self):
        """Get or create a database session."""
        if self._owns_session:
            return get_db_session()
        return self._session

    def upsert(self, document: VectorDocument) -> None:
        """Insert or update a document in the store.

        Args:
            document: The document to upsert.
        """
        metadata = document.metadata or {}

        # For new documents (no existing doc_id), let DB auto-generate ID
        # For updates, we would need the existing ID which is not tracked here
        chunk = RagDocumentChunk(
            tenant_id=metadata.get("tenant_id", 1),
            content=document.text,
            embedding=json.dumps(document.embedding),
            source_filename=metadata.get("source_filename"),
            source_type=metadata.get("source_type"),
            chunk_index=metadata.get("chunk_index"),
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        with self._get_session() as session:
            session.add(chunk)
            session.commit()

            logger.info(
                "rag.vector_store.upserted",
                extra={
                    "event": "rag.vector_store.upserted",
                    "doc_id": chunk.id,
                    "tenant_id": metadata.get("tenant_id", 1),
                },
            )

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        tenant_id: int = 1,
    ) -> list[tuple[VectorDocument, float]]:
        """Search for similar documents using vector similarity.

        Uses pgvector's cosine distance operator (<=>) for similarity.
        Falls back to recent chunks if vector search fails.

        Args:
            query_embedding: The query vector to search for.
            top_k: Number of results to return.
            tenant_id: The tenant ID for isolation.

        Returns:
            List of (document, score) tuples, sorted by similarity.
        """
        if not query_embedding:
            return self._fallback_to_recent(tenant_id=tenant_id, top_k=top_k)

        try:
            return self._pgvector_search(
                query_embedding=query_embedding,
                top_k=top_k,
                tenant_id=tenant_id,
            )
        except Exception as exc:
            logger.warning(
                "rag.vector_store.search_failed",
                extra={
                    "event": "rag.vector_store.search_failed",
                    "error": str(exc),
                    "tenant_id": tenant_id,
                },
            )
            return self._fallback_to_recent(tenant_id=tenant_id, top_k=top_k)

    def _pgvector_search(
        self,
        query_embedding: list[float],
        top_k: int,
        tenant_id: int,
    ) -> list[tuple[VectorDocument, float]]:
        """Perform pgvector similarity search."""
        # Build the embedding array string for pgvector
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        with self._get_session() as session:
            # Try pgvector cosine distance search
            # Using <=> operator for cosine distance (lower is more similar)
            try:
                query = text("""
                    SELECT id, content, embedding, source_filename, source_type,
                           chunk_index, metadata_json,
                           (embedding <=> :embedding::vector) as distance
                    FROM rag_document_chunks
                    WHERE tenant_id = :tenant_id
                    ORDER BY embedding <=> :embedding::vector
                    LIMIT :top_k
                """)

                result = session.execute(
                    query,
                    {
                        "embedding": embedding_str,
                        "tenant_id": tenant_id,
                        "top_k": top_k,
                    },
                )
            except Exception as exc:
                # Fallback: pgvector not available, use text-based fallback
                logger.warning(
                    "rag.vector_store.pgvector_unavailable",
                    extra={
                        "event": "rag.vector_store.pgvector_unavailable",
                        "error": str(exc),
                    },
                )
                raise

            documents = []
            for row in result:
                embedding = json.loads(row.embedding) if isinstance(row.embedding, str) else row.embedding
                metadata = json.loads(row.metadata_json) if row.metadata_json else {}

                doc = VectorDocument(
                    doc_id=str(row.id),
                    text=row.content,
                    embedding=embedding,
                    metadata={
                        **metadata,
                        "source_filename": row.source_filename,
                        "source_type": row.source_type,
                        "chunk_index": row.chunk_index,
                    },
                )
                # Convert distance to similarity (1 - distance for cosine)
                similarity = 1.0 - row.distance
                documents.append((doc, similarity))

            return documents

    def _fallback_to_recent(
        self,
        tenant_id: int,
        top_k: int,
    ) -> list[tuple[VectorDocument, float]]:
        """Fallback to recent chunks when vector search fails."""
        with self._get_session() as session:
            chunks = (
                session.query(RagDocumentChunk)
                .filter(RagDocumentChunk.tenant_id == tenant_id)
                .order_by(RagDocumentChunk.created_at.desc())
                .limit(top_k)
                .all()
            )

            documents = []
            for chunk in chunks:
                embedding = json.loads(chunk.embedding) if isinstance(chunk.embedding, str) else chunk.embedding
                metadata = json.loads(chunk.metadata_json) if chunk.metadata_json else {}

                doc = VectorDocument(
                    doc_id=str(chunk.id),
                    text=chunk.content,
                    embedding=embedding,
                    metadata={
                        **metadata,
                        "source_filename": chunk.source_filename,
                        "source_type": chunk.source_type,
                        "chunk_index": chunk.chunk_index,
                    },
                )
                documents.append((doc, 0.5))  # Default score for fallback

            return documents


class InMemoryVectorStore:
    """In-memory vector store fallback for testing/development."""

    def __init__(self):
        self._documents: list[VectorDocument] = []

    def upsert(self, document: VectorDocument) -> None:
        self._documents = [doc for doc in self._documents if doc.doc_id != document.doc_id]
        self._documents.append(document)

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        tenant_id: int = 1,
    ) -> list[tuple[VectorDocument, float]]:
        # Filter by tenant_id in metadata
        filtered = [doc for doc in self._documents if doc.metadata.get("tenant_id") == tenant_id]
        scored = [(doc, _cosine_similarity(query_embedding, doc.embedding)) for doc in filtered]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]
