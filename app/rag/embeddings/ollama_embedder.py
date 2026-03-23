"""Ollama-based embedding provider implementation with hash fallback."""

from __future__ import annotations

import hashlib
import logging
import os

import httpx

from app.core.config import get_config
from app.rag.embeddings.provider import EmbeddingProvider, EmbeddingResult

logger = logging.getLogger(__name__)

# Configuration
_cfg = get_config()
DEFAULT_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
DEFAULT_EMBEDDING_DIMS = int(os.getenv("RAG_EMBEDDING_DIMS", "768"))


def _strip_ollama_suffix(url: str) -> str:
    normalized = url.rstrip("/")
    lowered = normalized.lower()
    for suffix in ("/api/generate", "/api/embeddings", "/api/tags"):
        if lowered.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _ensure_embeddings_url(url: str) -> str:
    normalized = url.rstrip("/")
    if normalized.lower().endswith("/api/embeddings"):
        return normalized
    return f"{_strip_ollama_suffix(normalized)}/api/embeddings"


def _hash_embed(text: str, dims: int = DEFAULT_EMBEDDING_DIMS) -> list[float]:
    """Generate a deterministic hash-based embedding for fallback.

    This provides deterministic pseudo-random vectors for testing/fallback.
    Uses SHA-256 hash to generate consistent embeddings.

    Args:
        text: The text to embed.
        dims: Number of dimensions (default from config).

    Returns:
        A list of floats representing the hash-based vector.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # Generate values from hash bytes, normalized to [0, 1]
    nums = [float(digest[i % len(digest)]) / 255.0 for i in range(dims)]
    return nums


class OllamaEmbedder(EmbeddingProvider):
    """Embedding provider backed by Ollama embeddings endpoint.

    Falls back to hash-based embeddings when Ollama is unavailable.
    """

    def __init__(
        self,
        model_name: str | None = None,
        endpoint: str | None = None,
        embedding_dims: int = DEFAULT_EMBEDDING_DIMS,
    ) -> None:
        cfg = get_config()
        self.model_name = model_name or os.getenv("OLLAMA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        self.endpoint = _ensure_embeddings_url(endpoint or cfg.OLLAMA_EMBEDDING_URL)
        self.embedding_dims = embedding_dims
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Check if Ollama embedding service is available."""
        if self._available is not None:
            return self._available

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{_strip_ollama_suffix(self.endpoint)}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    self._available = any(self.model_name in name for name in model_names)
                    if not self._available:
                        logger.warning(
                            "rag.embedding.model_not_found",
                            extra={
                                "event": "rag.embedding.model_not_found",
                                "model": self.model_name,
                                "available_models": model_names,
                            },
                        )
                else:
                    self._available = False
        except Exception as exc:
            logger.warning(
                "rag.embedding.ollama_unavailable",
                extra={
                    "event": "rag.embedding.ollama_unavailable",
                    "error": str(exc),
                },
            )
            self._available = False

        return self._available

    def embed(self, text: str) -> EmbeddingResult:
        """Generate an embedding vector using Ollama or hash fallback.

        Args:
            text: The text to embed.

        Returns:
            EmbeddingResult with vector or hash fallback.
        """
        if not text or not text.strip():
            return EmbeddingResult(vector=[], model_name=self.model_name)

        # Try Ollama first
        if self.is_available():
            try:
                with httpx.Client(timeout=(5.0, 30.0)) as client:
                    response = client.post(
                        self.endpoint,
                        json={"model": self.model_name, "prompt": text},
                    )
                    response.raise_for_status()
                    body = response.json()
                    vector = body.get("embedding", [])
                    if isinstance(vector, list) and len(vector) > 0:
                        return EmbeddingResult(
                            vector=[float(item) for item in vector],
                            model_name=self.model_name,
                        )
            except Exception as exc:
                logger.warning(
                    "rag.embedding.failed",
                    extra={"event": "rag.embedding.failed", "error": str(exc)},
                )

        # Fallback to hash-based embedding
        logger.info(
            "rag.embedding.using_hash_fallback",
            extra={
                "event": "rag.embedding.using_hash_fallback",
                "detail": "Using hash embeddings. Install Ollama with nomic-embed-text for semantic search.",
            },
        )
        vector = _hash_embed(text, self.embedding_dims)
        return EmbeddingResult(vector=vector, model_name="hash-fallback-v1")


def get_embedder() -> OllamaEmbedder:
    """Get the default Ollama embedder instance.

    Returns:
        Configured OllamaEmbedder instance.
    """
    return OllamaEmbedder()
