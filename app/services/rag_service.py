"""RAG (Retrieval-Augmented Generation) Service for semantic search.

This service provides semantic search capabilities for the RIVO platform,
enabling agents to retrieve relevant context from knowledge bases and
negotiation history.

Architecture:
- Uses Ollama embeddings for semantic similarity (requires Ollama with embedding model)
- Falls back to hash embeddings when Ollama is unavailable
- Stores embeddings in PostgreSQL with JSON serialization
- Supports multi-tenant data isolation

Configuration:
    OLLAMA_EMBEDDING_MODEL: Model for embeddings (default: nomic-embed-text)
    OLLAMA_EMBEDDING_URL: Ollama embeddings endpoint
    RAG_EMBEDDING_DIMS: Embedding dimensions (default: 768)

Requirements:
    - Ollama installed and running (https://ollama.ai)
    - Embedding model pulled: ollama pull nomic-embed-text
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.core.config import get_config
from app.database.db import get_db_session
from app.database.models import Embedding, KnowledgeBase, NegotiationMemory

logger = logging.getLogger(__name__)

# Configuration
_cfg = get_config()
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = _cfg.OLLAMA_URL
OLLAMA_EMBEDDING_URL = os.getenv("OLLAMA_EMBEDDING_URL", _cfg.OLLAMA_EMBEDDING_URL)
RAG_EMBEDDING_DIMS = int(os.getenv("RAG_EMBEDDING_DIMS", "768"))
RAG_USE_REAL_EMBEDDINGS = os.getenv("RAG_USE_REAL_EMBEDDINGS", "true").lower() in {"1", "true", "yes", "on"}


def _strip_ollama_suffix(url: str) -> str:
    normalized = url.rstrip("/")
    lowered = normalized.lower()
    for suffix in ("/api/generate", "/api/embeddings", "/api/tags"):
        if lowered.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _ensure_embeddings_url(url: str, fallback_base: str) -> str:
    normalized = url.rstrip("/")
    if normalized.lower().endswith("/api/embeddings"):
        return normalized
    return f"{_strip_ollama_suffix(normalized or fallback_base)}/api/embeddings"


@dataclass
class RetrievedContext:
    """A retrieved context item from the knowledge base.
    
    Attributes:
        knowledge_id: The ID of the knowledge base entry.
        title: The title of the knowledge entry.
        content: The content of the knowledge entry.
        score: The similarity score (0-1, higher is more similar).
        source: The source of the knowledge entry.
    """
    knowledge_id: int
    title: str
    content: str
    score: float
    source: str = ""


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding providers.
    
    This allows for different embedding backends to be used
    interchangeably.
    """
    
    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.
        
        Args:
            text: The text to embed.
            
        Returns:
            A list of floats representing the embedding vector.
        """
        ...


def _hash_embed(text: str, dims: int = 16) -> list[float]:
    """Generate a deterministic hash-based embedding for fallback.
    
    WARNING: This is NOT a semantic embedding. It only provides
    deterministic pseudo-random vectors for testing/fallback.
    Use real embeddings for production.
    
    Args:
        text: The text to embed.
        dims: The number of dimensions (default: 16).
        
    Returns:
        A list of floats representing the hash-based vector.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    nums = [digest[i] / 255.0 for i in range(min(dims, 32))]
    return nums


def _cosine(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors.
    
    Args:
        a: First vector.
        b: Second vector.
        
    Returns:
        Cosine similarity score between -1 and 1.
    """
    if len(a) != len(b):
        logger.warning(
            "rag.vector_dimension_mismatch",
            extra={
                "event": "rag.vector_dimension_mismatch",
                "len_a": len(a),
                "len_b": len(b),
            },
        )
        # Pad shorter vector with zeros
        max_len = max(len(a), len(b))
        a = a + [0.0] * (max_len - len(a))
        b = b + [0.0] * (max_len - len(b))
    
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    
    if na == 0 or nb == 0:
        return 0.0
    
    return dot / (na * nb)


class OllamaEmbeddingProvider:
    """Embedding provider using Ollama's embedding API.
    
    This provider connects to a running Ollama instance to generate
    semantic embeddings using models like nomic-embed-text.
    
    Attributes:
        model: The embedding model name.
        endpoint: The Ollama API endpoint.
        timeout: Request timeout in seconds.
    """
    
    def __init__(
        self,
        model: str = OLLAMA_EMBEDDING_MODEL,
        endpoint: str = OLLAMA_EMBEDDING_URL,
        timeout: int = 30,
    ) -> None:
        """Initialize the Ollama embedding provider.
        
        Args:
            model: The embedding model to use.
            endpoint: The Ollama API endpoint.
            timeout: Request timeout in seconds.
        """
        self.model = model
        self.base_url = _strip_ollama_suffix(endpoint or OLLAMA_BASE_URL)
        self.endpoint = _ensure_embeddings_url(endpoint, fallback_base=self.base_url)
        self.timeout = timeout
        self._available: bool | None = None
    
    def is_available(self) -> bool:
        """Check if Ollama embedding service is available.
        
        Returns:
            True if Ollama is reachable and has the embedding model.
        """
        if self._available is not None:
            return self._available
        
        try:
            import requests
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5,
            )
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                # Check if embedding model is available
                self._available = any(self.model in name for name in model_names)
                if not self._available:
                    logger.warning(
                        "rag.embedding_model_not_found",
                        extra={
                            "event": "rag.embedding_model_not_found",
                            "model": self.model,
                            "available_models": model_names,
                        },
                    )
            else:
                self._available = False
        except Exception as exc:
            logger.warning(
                "rag.ollama_unavailable",
                extra={
                    "event": "rag.ollama_unavailable",
                    "error": str(exc),
                },
            )
            self._available = False
        
        return self._available
    
    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector using Ollama.
        
        Args:
            text: The text to embed.
            
        Returns:
            The embedding vector, or an empty list on failure.
        """
        if not text or not text.strip():
            return []
        
        try:
            import requests
            
            response = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "prompt": text,
                },
                timeout=(5, self.timeout),
            )
            response.raise_for_status()
            body = response.json()
            vector = body.get("embedding", [])
            
            if not isinstance(vector, list) or len(vector) == 0:
                logger.warning(
                    "rag.empty_embedding_response",
                    extra={
                        "event": "rag.empty_embedding_response",
                        "text_length": len(text),
                    },
                )
                return []
            
            return [float(item) for item in vector]
            
        except Exception as exc:
            logger.warning(
                "rag.embedding_failed",
                extra={
                    "event": "rag.embedding_failed",
                    "error": str(exc),
                    "text_length": len(text),
                },
            )
            return []


class RAGService:
    """RAG service for semantic search and knowledge retrieval.
    
    This service provides:
    - Knowledge base ingestion with semantic embeddings
    - Negotiation memory storage and retrieval
    - Semantic search across all stored knowledge
    
    The service uses real Ollama embeddings when available,
    falling back to hash-based embeddings for testing.
    
    Example:
        >>> rag = RAGService()
        >>> # Ingest knowledge
        >>> kb_id = rag.ingest_knowledge(
        ...     tenant_id=1,
        ...     entity_type="deal",
        ...     entity_id=42,
        ...     title="Customer preferences",
        ...     content="Customer prefers annual billing",
        ... )
        >>> # Retrieve relevant context
        >>> contexts = rag.retrieve(
        ...     tenant_id=1,
        ...     query="What are the billing preferences?",
        ...     top_k=3,
        ... )
    """
    
    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        use_real_embeddings: bool = RAG_USE_REAL_EMBEDDINGS,
    ) -> None:
        """Initialize the RAG service.
        
        Args:
            embedding_provider: Custom embedding provider (for testing).
            use_real_embeddings: Whether to use real Ollama embeddings.
        """
        self._provider = embedding_provider
        self._use_real_embeddings = use_real_embeddings
        self._ollama_provider: OllamaEmbeddingProvider | None = None
    
    @property
    def provider(self) -> EmbeddingProvider:
        """Get the embedding provider.
        
        Lazily initializes the Ollama provider on first use.
        
        Returns:
            The embedding provider instance.
        """
        if self._provider is not None:
            return self._provider
        
        if self._use_real_embeddings:
            if self._ollama_provider is None:
                self._ollama_provider = OllamaEmbeddingProvider()
            
            if self._ollama_provider.is_available():
                return self._ollama_provider
        
        # Fallback to hash embeddings
        logger.info(
            "rag.using_hash_embeddings",
            extra={
                "event": "rag.using_hash_embeddings",
                "detail": "Using hash embeddings. Install Ollama with nomic-embed-text for semantic search.",
            },
        )
        return _HashEmbedProvider()
    
    def _embed(self, text: str) -> list[float]:
        """Generate an embedding for the given text.
        
        Args:
            text: The text to embed.
            
        Returns:
            The embedding vector.
        """
        return self.provider.embed(text)
    
    def _get_model_name(self) -> str:
        """Get the current embedding model name.
        
        Returns:
            The model name string.
        """
        if isinstance(self.provider, OllamaEmbeddingProvider):
            return self.provider.model
        elif isinstance(self.provider, _HashEmbedProvider):
            return "hash-embedding-v1"
        return "unknown"
    
    def ingest_knowledge(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        title: str,
        content: str,
        source: str = "sales_agent",
    ) -> int:
        """Ingest knowledge into the knowledge base.
        
        This method:
        1. Generates an embedding for the content
        2. Stores the knowledge entry
        3. Stores the embedding vector
        
        Args:
            tenant_id: The tenant ID for multi-tenant isolation.
            entity_type: The type of entity (e.g., "deal", "lead").
            entity_id: The ID of the related entity.
            title: The title of the knowledge entry.
            content: The content to store and embed.
            source: The source agent or system.
            
        Returns:
            The ID of the created knowledge entry.
        """
        if not content or not content.strip():
            logger.warning(
                "rag.empty_content",
                extra={
                    "event": "rag.empty_content",
                    "tenant_id": tenant_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                },
            )
            return 0
        
        vector = self._embed(content)
        model_name = self._get_model_name()
        
        with get_db_session() as session:
            # Check for existing entry
            matches = (
                session.query(KnowledgeBase)
                .filter(KnowledgeBase.tenant_id == tenant_id)
                .filter(KnowledgeBase.entity_type == entity_type)
                .filter(KnowledgeBase.entity_id == entity_id)
                .filter(KnowledgeBase.title == title)
                .filter(KnowledgeBase.content == content)
                .filter(KnowledgeBase.source == source)
                .order_by(KnowledgeBase.id.asc())
                .all()
            )

            kb: KnowledgeBase
            if matches:
                kb = matches[0]
                # Cleanup stale duplicates
                stale_ids = [row.id for row in matches[1:]]
                if stale_ids:
                    session.query(Embedding).filter(
                        Embedding.knowledge_base_id.in_(stale_ids)
                    ).delete(synchronize_session=False)
                    session.query(KnowledgeBase).filter(
                        KnowledgeBase.id.in_(stale_ids)
                    ).delete(synchronize_session=False)
            else:
                kb = KnowledgeBase(
                    tenant_id=tenant_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    title=title,
                    content=content,
                    source=source,
                )
                session.add(kb)
                session.flush()

            # Update or create embedding
            emb = (
                session.query(Embedding)
                .filter(Embedding.tenant_id == tenant_id)
                .filter(Embedding.knowledge_base_id == kb.id)
                .filter(Embedding.model == model_name)
                .first()
            )
            
            if not emb:
                emb = Embedding(
                    tenant_id=tenant_id,
                    knowledge_base_id=kb.id,
                    vector=json.dumps(vector),
                    model=model_name,
                )
                session.add(emb)
            else:
                emb.vector = json.dumps(vector)

            session.commit()
            
            logger.info(
                "rag.knowledge_ingested",
                extra={
                    "event": "rag.knowledge_ingested",
                    "knowledge_id": kb.id,
                    "tenant_id": tenant_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "model": model_name,
                    "vector_dims": len(vector),
                },
            )
            
            return kb.id

    def ingest_negotiation_memory(
        self,
        tenant_id: int,
        deal_id: int,
        transcript: str,
        summary: str,
        objection_tags: str = "",
    ) -> int:
        """Ingest negotiation memory for future reference.
        
        This stores the negotiation transcript and summary for
        future agents to reference during similar negotiations.
        
        Args:
            tenant_id: The tenant ID for multi-tenant isolation.
            deal_id: The ID of the related deal.
            transcript: The full negotiation transcript.
            summary: A summary of the negotiation.
            objection_tags: Comma-separated objection tags.
            
        Returns:
            The ID of the created negotiation memory entry.
        """
        with get_db_session() as session:
            row = NegotiationMemory(
                tenant_id=tenant_id,
                deal_id=deal_id,
                transcript=transcript,
                summary=summary,
                objection_tags=objection_tags,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            
            # Also ingest summary into knowledge base
            self.ingest_knowledge(
                tenant_id=tenant_id,
                entity_type="deal",
                entity_id=deal_id,
                title=f"Negotiation summary #{row.id}",
                content=summary,
                source="negotiation_memory",
            )
            
            logger.info(
                "rag.negotiation_memory_ingested",
                extra={
                    "event": "rag.negotiation_memory_ingested",
                    "memory_id": row.id,
                    "tenant_id": tenant_id,
                    "deal_id": deal_id,
                },
            )
            
            return row.id

    def retrieve(
        self,
        tenant_id: int,
        query: str,
        top_k: int = 3,
        entity_type: str | None = None,
        source: str | None = None,
    ) -> list[RetrievedContext]:
        """Retrieve relevant context from the knowledge base.
        
        This method performs semantic search to find the most
        relevant knowledge entries for the given query.
        
        Args:
            tenant_id: The tenant ID for multi-tenant isolation.
            query: The search query.
            top_k: Maximum number of results to return.
            entity_type: Optional filter by entity type.
            source: Optional filter by source.
            
        Returns:
            A list of RetrievedContext objects, sorted by relevance.
        """
        if not query or not query.strip():
            return []
        
        qv = self._embed(query)
        if not qv:
            logger.warning(
                "rag.query_embedding_failed",
                extra={
                    "event": "rag.query_embedding_failed",
                    "query_length": len(query),
                },
            )
            return []
        
        contexts: list[RetrievedContext] = []
        
        with get_db_session() as session:
            query_obj = (
                session.query(KnowledgeBase, Embedding)
                .join(Embedding, Embedding.knowledge_base_id == KnowledgeBase.id)
                .filter(KnowledgeBase.tenant_id == tenant_id)
            )
            
            if entity_type:
                query_obj = query_obj.filter(KnowledgeBase.entity_type == entity_type)
            if source:
                query_obj = query_obj.filter(KnowledgeBase.source == source)
            
            rows = query_obj.all()
            
            for kb, emb in rows:
                try:
                    ev = json.loads(emb.vector)
                except (json.JSONDecodeError, TypeError):
                    continue
                
                score = _cosine(qv, ev)
                contexts.append(RetrievedContext(
                    knowledge_id=kb.id,
                    title=kb.title,
                    content=kb.content,
                    score=score,
                    source=kb.source,
                ))

        # Sort by score descending
        contexts.sort(key=lambda x: x.score, reverse=True)
        
        logger.info(
            "rag.context_retrieved",
            extra={
                "event": "rag.context_retrieved",
                "tenant_id": tenant_id,
                "query_length": len(query),
                "total_candidates": len(contexts),
                "returned": min(top_k, len(contexts)),
                "top_score": contexts[0].score if contexts else 0.0,
            },
        )
        
        return contexts[:top_k]


class _HashEmbedProvider:
    """Hash-based embedding provider for fallback/testing."""
    
    @property
    def model(self) -> str:
        return "hash-embedding-v1"
    
    def embed(self, text: str) -> list[float]:
        return _hash_embed(text)


# Singleton instance for convenience
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """Get the singleton RAG service instance.
    
    Returns:
        The RAGService singleton.
    """
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
