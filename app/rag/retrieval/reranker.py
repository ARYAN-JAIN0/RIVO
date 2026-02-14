"""Simple reranker for retrieved documents."""

from __future__ import annotations

from app.rag.retrieval.retriever import RetrievedDocument


class Reranker:
    """Deterministic reranker using lexical overlap with query tokens."""

    def rerank(self, query: str, documents: list[RetrievedDocument]) -> list[RetrievedDocument]:
        query_tokens = {token.lower() for token in query.split() if token.strip()}
        if not query_tokens:
            return documents

        def _score(item: RetrievedDocument) -> float:
            doc_tokens = {token.lower() for token in item.document.text.split() if token.strip()}
            overlap = len(query_tokens.intersection(doc_tokens))
            return (item.score * 0.8) + (overlap * 0.2)

        return sorted(documents, key=_score, reverse=True)
