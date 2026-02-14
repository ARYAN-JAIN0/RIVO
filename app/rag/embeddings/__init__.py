"""Embedding provider package."""

from app.rag.embeddings.ollama_embedder import OllamaEmbedder
from app.rag.embeddings.provider import EmbeddingProvider, EmbeddingResult

__all__ = ["EmbeddingProvider", "EmbeddingResult", "OllamaEmbedder"]
