"""PGVector store contract with in-memory fallback implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Any


@dataclass
class VectorDocument:
    doc_id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sqrt(sum(x * x for x in a))
    norm_b = sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class PGVectorStore:
    """Store contract for pgvector-backed retrieval.

    Phase 1 uses an in-memory fallback to define behavior before DB activation.
    """

    def __init__(self) -> None:
        self._documents: list[VectorDocument] = []

    def upsert(self, document: VectorDocument) -> None:
        self._documents = [doc for doc in self._documents if doc.doc_id != document.doc_id]
        self._documents.append(document)

    def similarity_search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[VectorDocument, float]]:
        scored = [(doc, _cosine_similarity(query_embedding, doc.embedding)) for doc in self._documents]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]
