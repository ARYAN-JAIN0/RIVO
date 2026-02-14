"""Embedding provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    model_name: str


class EmbeddingProvider(ABC):
    """Contract for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> EmbeddingResult:
        raise NotImplementedError
