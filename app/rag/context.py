"""RAG context builder for formatting retrieved documents."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Configuration
MAX_CONTEXT_TOKENS = int(os.getenv("RAG_MAX_CONTEXT_TOKENS", "2000"))


@dataclass
class FormattedChunk:
    """A formatted chunk with source information."""
    content: str
    source: str
    score: float


def _count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken when available.

    Uses tiktoken with cl100k_base encoding for accurate token counting.
    Falls back to whitespace splitting if tiktoken is not available.

    Args:
        text: Input text.

    Returns:
        Token count.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Fallback to simple whitespace splitting
        return len(text.split())


def _format_chunk(doc_id: str, content: str, metadata: dict, score: float) -> FormattedChunk:
    """Format a chunk with source information.

    Args:
        doc_id: Document ID.
        content: Chunk content.
        metadata: Chunk metadata.
        score: Similarity score.

    Returns:
        Formatted chunk with source.
    """
    source_filename = metadata.get("source_filename", "unknown")
    chunk_index = metadata.get("chunk_index")

    source_parts = [source_filename]
    if chunk_index is not None:
        source_parts.append(f"chunk {chunk_index}")
    source_parts.append(f"score: {score:.2f}")

    source = " | ".join(source_parts)

    return FormattedChunk(
        content=content,
        source=source,
        score=score,
    )


def _deduplicate_chunks(chunks: list[FormattedChunk]) -> list[FormattedChunk]:
    """Remove duplicate chunks based on content.

    Args:
        chunks: List of formatted chunks.

    Returns:
        Deduplicated list of chunks.
    """
    seen_content: set[str] = set()
    unique_chunks: list[FormattedChunk] = []

    for chunk in chunks:
        # Normalize content for comparison
        normalized = chunk.content.strip().lower()
        if normalized not in seen_content:
            seen_content.add(normalized)
            unique_chunks.append(chunk)

    return unique_chunks


def _select_chunks_by_tokens(
    chunks: list[FormattedChunk],
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> list[FormattedChunk]:
    """Select chunks that fit within token budget.

    Args:
        chunks: List of formatted chunks.
        max_tokens: Maximum tokens allowed.

    Returns:
        Selected chunks that fit within budget.
    """
    selected: list[FormattedChunk] = []
    current_tokens = 0

    for chunk in chunks:
        chunk_tokens = _count_tokens(chunk.content)
        if current_tokens + chunk_tokens > max_tokens:
            break
        selected.append(chunk)
        current_tokens += chunk_tokens

    return selected


def build_rag_context(
    retrieved_documents: list,
    max_context_tokens: int = MAX_CONTEXT_TOKENS,
    include_sources: bool = True,
) -> str:
    """Build RAG context string from retrieved documents.

    Formats retrieved documents into a context string suitable for
    LLM consumption. Handles deduplication and token limits.

    Args:
        retrieved_documents: List of retrieved documents from retriever.
        max_context_tokens: Maximum tokens for context.
        include_sources: Whether to include source citations.

    Returns:
        Formatted context string, or empty string on failure.
    """
    if not retrieved_documents:
        logger.info(
            "rag.context.no_documents",
            extra={"event": "rag.context.no_documents"},
        )
        return ""

    try:
        # Format chunks
        formatted_chunks = []
        for doc in retrieved_documents:
            formatted = _format_chunk(
                doc_id=doc.document_id,
                content=doc.content,
                metadata=doc.metadata or {},
                score=doc.score,
            )
            formatted_chunks.append(formatted)

        # Deduplicate
        unique_chunks = _deduplicate_chunks(formatted_chunks)

        # Sort by score (highest first)
        unique_chunks.sort(key=lambda x: x.score, reverse=True)

        # Select by token budget
        selected_chunks = _select_chunks_by_tokens(unique_chunks, max_context_tokens)

        if not selected_chunks:
            return ""

        # Build context string
        context_parts = []

        for chunk in selected_chunks:
            if include_sources:
                context_parts.append(f"[Source: {chunk.source}]\n{chunk.content}")
            else:
                context_parts.append(chunk.content)

        context = "\n\n---\n\n".join(context_parts)

        logger.info(
            "rag.context.built",
            extra={
                "event": "rag.context.built",
                "total_chunks": len(retrieved_documents),
                "unique_chunks": len(unique_chunks),
                "selected_chunks": len(selected_chunks),
                "context_length": len(context),
            },
        )

        return context

    except Exception as exc:
        logger.error(
            "rag.context.error",
            extra={
                "event": "rag.context.error",
                "error": str(exc),
            },
        )
        return ""


def build_rag_context_with_sources(
    retrieved_documents: list,
    max_context_tokens: int = MAX_CONTEXT_TOKENS,
) -> tuple[str, list[dict]]:
    """Build RAG context with source metadata.

    Args:
        retrieved_documents: List of retrieved documents.
        max_context_tokens: Maximum tokens for context.

    Returns:
        Tuple of (context_string, sources_list).
    """
    if not retrieved_documents:
        return "", []

    try:
        # Format chunks
        formatted_chunks = []
        for doc in retrieved_documents:
            formatted = _format_chunk(
                doc_id=doc.document_id,
                content=doc.content,
                metadata=doc.metadata or {},
                score=doc.score,
            )
            formatted_chunks.append(formatted)

        # Deduplicate
        unique_chunks = _deduplicate_chunks(formatted_chunks)

        # Sort by score
        unique_chunks.sort(key=lambda x: x.score, reverse=True)

        # Select by token budget
        selected_chunks = _select_chunks_by_tokens(unique_chunks, max_context_tokens)

        if not selected_chunks:
            return "", []

        # Build context and sources
        context_parts = []
        sources = []

        for chunk in selected_chunks:
            context_parts.append(f"[Source: {chunk.source}]\n{chunk.content}")
            sources.append({
                "source": chunk.source,
                "score": chunk.score,
            })

        context = "\n\n---\n\n".join(context_parts)

        return context, sources

    except Exception as exc:
        logger.error(
            "rag.context.sources_error",
            extra={
                "event": "rag.context.sources_error",
                "error": str(exc),
            },
        )
        return "", []
