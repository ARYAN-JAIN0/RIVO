"""RAG API endpoints."""

from __future__ import annotations

import logging

from app.api._compat import APIRouter, Header, HTTPException, UploadFile, status
from app.api.v1.endpoints import _authorize
from app.rag.context import build_rag_context_with_sources
from app.rag.ingestion import get_ingestion_pipeline
from app.rag.retrieval import get_retriever
from app.schemas.rag import RagIngestResponse, RagQueryRequest, RagQueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/ingest")
async def ingest_document(
    file: UploadFile,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """Ingest a document into the RAG system.

    Args:
        file: Uploaded file (multipart form data).
        authorization: Bearer token for authentication.

    Returns:
        Ingestion result with chunk count.
    """
    user = _authorize(authorization, scopes=["rag.ingest"])
    tenant_id = user.tenant_id
    try:
        # Read file content from UploadFile
        file_content = await file.read()
        filename = file.filename or "unknown"
        
        pipeline = get_ingestion_pipeline()
        chunk_ids = pipeline.ingest_document(
            file_content=file_content,
            filename=filename,
            tenant_id=tenant_id,
        )

        return RagIngestResponse(
            success=True,
            chunks_created=len(chunk_ids),
            filename=filename,
        ).model_dump()

    except ValueError as exc:
        # Client error - bad request
        logger.warning(
            "rag.api.ingest_value_error",
            extra={
                "event": "rag.api.ingest_value_error",
                "error": str(exc),
                "filename": filename,
            },
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        # Server error - log and return failure response
        logger.error(
            "rag.api.ingest_error",
            extra={
                "event": "rag.api.ingest_error",
                "error": str(exc),
                "filename": filename,
            },
        )
        return RagIngestResponse(
            success=False,
            chunks_created=0,
            filename=filename,
            error=str(exc),
        ).model_dump()


@router.post("/query")
async def query_rag(
    request: RagQueryRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """Query the RAG system.

    Args:
        request: Query request with query, top_k, etc.
        authorization: Bearer token for authentication.

    Returns:
        Query result with context and sources.
    """
    user = _authorize(authorization, scopes=["rag.query"])
    tenant_id = request.tenant_id or user.tenant_id
    try:
        # Retrieve documents
        retriever = get_retriever()
        documents = retriever.retrieve(
            query=request.query,
            top_k=request.top_k,
            tenant_id=tenant_id,
        )

        if not documents:
            return RagQueryResponse(
                success=True,
                query=request.query,
                context="",
                sources=[],
                result_count=0,
            ).model_dump()

        # Build context
        context, sources = build_rag_context_with_sources(
            retrieved_documents=documents,
            max_context_tokens=request.max_context_tokens,
        )

        return RagQueryResponse(
            success=True,
            query=request.query,
            context=context,
            sources=sources,
            result_count=len(documents),
        ).model_dump()

    except Exception as exc:
        logger.error(
            "rag.api.query_error",
            extra={
                "event": "rag.api.query_error",
                "error": str(exc),
                "query": request.query,
            },
        )
        return RagQueryResponse(
            success=False,
            query=request.query,
            context="",
            sources=[],
            result_count=0,
            error=str(exc),
        ).model_dump()


@router.get("/health")
async def rag_health() -> dict:
    """Health check for RAG system.

    Returns:
        Health status.
    """
    return {
        "status": "healthy",
        "service": "RAG",
    }
