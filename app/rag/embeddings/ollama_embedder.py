"""Ollama-based embedding provider implementation."""

from __future__ import annotations

import logging

import requests

from app.core.config import get_config
from app.rag.embeddings.provider import EmbeddingProvider, EmbeddingResult

logger = logging.getLogger(__name__)


class OllamaEmbedder(EmbeddingProvider):
    """Embedding provider backed by Ollama embeddings endpoint."""

    def __init__(self, model_name: str | None = None, endpoint: str | None = None) -> None:
        cfg = get_config()
        self.model_name = model_name or cfg.OLLAMA_MODEL
        self.endpoint = endpoint or cfg.OLLAMA_URL.replace("/api/generate", "/api/embeddings")

    def embed(self, text: str) -> EmbeddingResult:
        payload = {"model": self.model_name, "prompt": text}
        try:
            response = requests.post(self.endpoint, json=payload, timeout=(5, 30))
            response.raise_for_status()
            body = response.json()
            vector = body.get("embedding", [])
            if not isinstance(vector, list):
                vector = []
            return EmbeddingResult(vector=[float(item) for item in vector], model_name=self.model_name)
        except Exception as exc:  # pragma: no cover - external dependency path.
            logger.warning("rag.embedding.failed", extra={"event": "rag.embedding.failed", "error": str(exc)})
            return EmbeddingResult(vector=[], model_name=self.model_name)
