from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

from app.database.db import get_db_session
from app.database.models import Embedding, KnowledgeBase, NegotiationMemory

logger = logging.getLogger(__name__)


@dataclass
class RetrievedContext:
    knowledge_id: int
    title: str
    content: str
    score: float


def _hash_embed(text: str, dims: int = 16) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    nums = [digest[i] / 255.0 for i in range(dims)]
    return nums


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class RAGService:
    """PGVector-compatible abstraction with JSON-vector fallback for local portability."""

    def ingest_knowledge(self, tenant_id: int, entity_type: str, entity_id: int, title: str, content: str, source: str = "sales_agent") -> int:
        vector = _hash_embed(content)
        with get_db_session() as session:
            kb = KnowledgeBase(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                title=title,
                content=content,
                source=source,
            )
            session.add(kb)
            session.commit()
            session.refresh(kb)

            emb = Embedding(
                tenant_id=tenant_id,
                knowledge_base_id=kb.id,
                vector=json.dumps(vector),
                model="hash-embedding-v1",
            )
            session.add(emb)
            session.commit()
            return kb.id

    def ingest_negotiation_memory(self, tenant_id: int, deal_id: int, transcript: str, summary: str, objection_tags: str = "") -> int:
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
            # also ingest summary into kb
            self.ingest_knowledge(tenant_id, "deal", deal_id, f"Negotiation summary #{row.id}", summary, source="negotiation_memory")
            return row.id

    def retrieve(self, tenant_id: int, query: str, top_k: int = 3) -> list[RetrievedContext]:
        qv = _hash_embed(query)
        contexts: list[RetrievedContext] = []
        with get_db_session() as session:
            rows = (
                session.query(KnowledgeBase, Embedding)
                .join(Embedding, Embedding.knowledge_base_id == KnowledgeBase.id)
                .filter(KnowledgeBase.tenant_id == tenant_id)
                .all()
            )
            for kb, emb in rows:
                try:
                    ev = json.loads(emb.vector)
                except Exception:
                    continue
                score = _cosine(qv, ev)
                contexts.append(RetrievedContext(knowledge_id=kb.id, title=kb.title, content=kb.content, score=score))

        contexts.sort(key=lambda x: x.score, reverse=True)
        return contexts[:top_k]
