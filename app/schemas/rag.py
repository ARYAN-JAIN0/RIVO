"""Pydantic schemas for RAG API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RagIngestRequest(BaseModel):
    """Request to ingest a document."""
    filename: str = Field(..., description="Original filename")
    tenant_id: int = Field(default=1, description="Tenant ID for isolation")


class RagIngestResponse(BaseModel):
    """Response from document ingestion."""
    success: bool = Field(..., description="Whether ingestion succeeded")
    chunks_created: int = Field(default=0, description="Number of chunks created")
    filename: str = Field(..., description="Original filename")
    error: str | None = Field(default=None, description="Error message if failed")


class RagQueryRequest(BaseModel):
    """Request to query the RAG system."""
    query: str = Field(..., min_length=1, description="Search query")
    tenant_id: int = Field(default=1, description="Tenant ID for isolation")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results")
    max_context_tokens: int = Field(
        default=2000,
        ge=100,
        le=8000,
        description="Maximum tokens for context",
    )


class RagQueryResponse(BaseModel):
    """Response from RAG query."""
    success: bool = Field(..., description="Whether query succeeded")
    query: str = Field(..., description="Original query")
    context: str = Field(default="", description="Formatted context for LLM")
    sources: list[dict] = Field(default_factory=list, description="Source metadata")
    result_count: int = Field(default=0, description="Number of chunks retrieved")
    error: str | None = Field(default=None, description="Error message if failed")


class RagSource(BaseModel):
    """Source metadata for a retrieved chunk."""
    source: str
    score: float


class RagChunkInfo(BaseModel):
    """Information about a stored chunk."""
    id: int
    content: str
    source_filename: str | None
    source_type: str | None
    chunk_index: int | None
    created_at: str
