"""RAG document ingestion pipeline.

Handles text extraction from various file formats and semantic chunking
for storage in the vector database.
"""

from __future__ import annotations

import io
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from app.database.db import get_db_session
from app.database.models import RagDocumentChunk
from app.rag.embeddings.ollama_embedder import get_embedder

logger = logging.getLogger(__name__)

# Configuration with sensible defaults
CHUNK_SIZE_TOKENS = int(os.getenv("RAG_CHUNK_SIZE_TOKENS", "500"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("RAG_CHUNK_OVERLAP_TOKENS", "75"))


@dataclass
class ChunkResult:
    """Result of document chunking."""
    content: str
    chunk_index: int
    metadata: dict[str, Any]


def _extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF using pdfplumber or PyPDF2.

    Args:
        file_content: Raw PDF bytes.

    Returns:
        Extracted text content.
    """
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages)
    except ImportError:
        pass

    # Fallback to PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_content))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)
    except ImportError:
        logger.warning(
            "rag.ingestion.pdf_library_missing",
            extra={
                "event": "rag.ingestion.pdf_library_missing",
                "detail": "Install pdfplumber or PyPDF2 for PDF extraction",
            },
        )
    except Exception as exc:
        logger.warning(
            "rag.ingestion.pdf_extraction_failed",
            extra={
                "event": "rag.ingestion.pdf_extraction_failed",
                "error": str(exc),
            },
        )

    return ""


def _extract_text_from_txt(file_content: bytes) -> str:
    """Extract text from plain text file.

    Args:
        file_content: Raw text file bytes.

    Returns:
        Text content.
    """
    try:
        # Try UTF-8 first
        return file_content.decode("utf-8")
    except UnicodeDecodeError:
        # Fallback to latin-1
        return file_content.decode("latin-1")


def _extract_text_from_md(file_content: bytes) -> str:
    """Extract text from Markdown file.

    Args:
        file_content: Raw markdown file bytes.

    Returns:
        Text content (markdown preserved).
    """
    try:
        return file_content.decode("utf-8")
    except UnicodeDecodeError:
        return file_content.decode("latin-1")


def _extract_text(file_content: bytes, file_type: str) -> str:
    """Extract text based on file type.

    Args:
        file_content: Raw file bytes.
        file_type: File extension (pdf, txt, md).

    Returns:
        Extracted text content.
    """
    file_type = file_type.lower().lstrip(".")

    if file_type == "pdf":
        return _extract_text_from_pdf(file_content)
    elif file_type in ("txt", "text"):
        return _extract_text_from_txt(file_content)
    elif file_type in ("md", "markdown"):
        return _extract_text_from_md(file_content)
    else:
        logger.warning(
            "rag.ingestion.unsupported_file_type",
            extra={
                "event": "rag.ingestion.unsupported_file_type",
                "file_type": file_type,
            },
        )
        return ""


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


def _semantic_chunking(
    text: str,
    chunk_size_tokens: int = CHUNK_SIZE_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> list[ChunkResult]:
    """Split text into semantically meaningful chunks.

    Uses simple token-based chunking with overlap.

    Args:
        text: Input text to chunk.
        chunk_size_tokens: Target chunk size in tokens.
        overlap_tokens: Overlap between chunks in tokens.

    Returns:
        List of chunk results with content and metadata.
    """
    if not text or not text.strip():
        return []

    # Split by paragraphs first (preserves semantic units)
    paragraphs = text.split("\n\n")
    chunks: list[ChunkResult] = []
    current_chunk_content: list[str] = []
    current_tokens = 0
    chunk_index = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_tokens = _count_tokens(para)

        # If single paragraph exceeds chunk size, split by sentences
        if para_tokens > chunk_size_tokens:
            # Flush current chunk first
            if current_chunk_content:
                chunks.append(
                    ChunkResult(
                        content="\n\n".join(current_chunk_content),
                        chunk_index=chunk_index,
                        metadata={},
                    )
                )
                chunk_index += 1
                current_chunk_content = []
                current_tokens = 0

            # Split long paragraph by sentences
            sentences = para.split(". ")
            temp_chunk: list[str] = []
            temp_tokens = 0

            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue

                sent_tokens = _count_tokens(sent)

                if temp_tokens + sent_tokens > chunk_size_tokens:
                    # Flush temp chunk
                    if temp_chunk:
                        chunks.append(
                            ChunkResult(
                                content=". ".join(temp_chunk),
                                chunk_index=chunk_index,
                                metadata={},
                            )
                        )
                        chunk_index += 1
                        temp_chunk = []
                        temp_tokens = 0

                temp_chunk.append(sent)
                temp_tokens += sent_tokens

            # Flush remaining temp chunk
            if temp_chunk:
                chunks.append(
                    ChunkResult(
                        content=". ".join(temp_chunk),
                        chunk_index=chunk_index,
                        metadata={},
                    )
                )
                chunk_index += 1

        elif current_tokens + para_tokens > chunk_size_tokens:
            # Flush current chunk
            chunks.append(
                ChunkResult(
                    content="\n\n".join(current_chunk_content),
                    chunk_index=chunk_index,
                    metadata={},
                )
            )
            chunk_index += 1

            # Keep overlap from previous chunk (simplified - last paragraph)
            overlap_words: list[str] = []
            if overlap_tokens > 0 and current_chunk_content:
                last_para_words = current_chunk_content[-1].split()
                overlap_word_count = min(len(last_para_words), overlap_tokens)
                overlap_words = last_para_words[-overlap_word_count:]

            if overlap_words:
                current_chunk_content = [" ".join(overlap_words), para]
                current_tokens = _count_tokens(" ".join(overlap_words)) + para_tokens
            else:
                current_chunk_content = [para]
                current_tokens = para_tokens

        else:
            # Add to current chunk
            current_chunk_content.append(para)
            current_tokens += para_tokens

    # Flush final chunk
    if current_chunk_content:
        chunks.append(
            ChunkResult(
                content="\n\n".join(current_chunk_content),
                chunk_index=chunk_index,
                metadata={},
            )
        )

    return chunks


class IngestionPipeline:
    """Document ingestion pipeline for RAG.

    Handles file extraction, chunking, embedding, and storage.
    """

    def __init__(self):
        """Initialize the ingestion pipeline."""
        self._embedder = get_embedder()

    def ingest_document(
        self,
        file_content: bytes,
        filename: str,
        tenant_id: int = 1,
    ) -> list[int]:
        """Ingest a document into the RAG system.

        Args:
            file_content: Raw file bytes.
            filename: Original filename.
            tenant_id: Tenant ID for isolation.

        Returns:
            List of created chunk IDs.
        """
        # Determine file type
        file_type = filename.split(".")[-1] if "." in filename else "txt"

        # Extract text
        text = _extract_text(file_content, file_type)
        if not text:
            logger.warning(
                "rag.ingestion.no_text_extracted",
                extra={
                    "event": "rag.ingestion.no_text_extracted",
                    "source_filename": filename,
                },
            )
            return []

        # Chunk the text
        chunks = _semantic_chunking(text)
        if not chunks:
            return []

        logger.info(
            "rag.ingestion.processing",
            extra={
                "event": "rag.ingestion.processing",
                "filename": filename,
                "chunk_count": len(chunks),
                "tenant_id": tenant_id,
            },
        )

        # Process chunks
        chunk_ids = []
        with get_db_session() as session:
            for chunk_result in chunks:
                # Generate embedding
                embedding_result = self._embedder.embed(chunk_result.content)
                vector = embedding_result.vector

                if not vector:
                    logger.warning(
                        "rag.ingestion.skip_empty_embedding",
                        extra={
                            "event": "rag.ingestion.skip_empty_embedding",
                            "chunk_index": chunk_result.chunk_index,
                        },
                    )
                    continue

                # Store chunk
                chunk = RagDocumentChunk(
                    tenant_id=tenant_id,
                    content=chunk_result.content,
                    embedding=json.dumps(vector),
                    source_filename=filename,
                    source_type=file_type,
                    chunk_index=chunk_result.chunk_index,
                    metadata_json=json.dumps(chunk_result.metadata) if chunk_result.metadata else None,
                )
                session.add(chunk)
                session.flush()
                chunk_ids.append(chunk.id)

            session.commit()

        logger.info(
            "rag.ingestion.completed",
            extra={
                "event": "rag.ingestion.completed",
                "filename": filename,
                "chunks_created": len(chunk_ids),
                "tenant_id": tenant_id,
            },
        )

        return chunk_ids


def get_ingestion_pipeline() -> IngestionPipeline:
    """Get the default ingestion pipeline instance.

    Returns:
        Configured IngestionPipeline instance.
    """
    return IngestionPipeline()
