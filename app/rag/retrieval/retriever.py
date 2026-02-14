"""Retriever abstraction for RAG flows."""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.embeddings.provider import EmbeddingProvider
from app.rag.vector_store.pgvector_store import PGVectorStore, VectorDocument


@dataclass(frozen=True)
class RetrievedDocument:
    document: VectorDocument
    score: float


class Retriever:
    """Embedding + vector-store retrieval coordinator."""

    def __init__(self, embedding_provider: EmbeddingProvider, vector_store: PGVectorStore) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedDocument]:
        embedding = self.embedding_provider.embed(query).vector
        matches = self.vector_store.similarity_search(embedding, top_k=top_k)
        return [RetrievedDocument(document=doc, score=score) for doc, score in matches]
