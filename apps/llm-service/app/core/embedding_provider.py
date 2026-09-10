from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import settings


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed one or more texts into vectors, in the given order."""


class FastEmbedProvider(EmbeddingProvider):
    """Local, ONNX-based embeddings (fastembed) — the default while no GPU
    is available. Deliberately not PyTorch/transformers: loading even a
    small (~420MB) transformers model crashed with MemoryError on this
    low-RAM dev machine; fastembed's quantized ONNX runtime has a much
    lower peak memory footprint.

    Swapping to a different embedding backend (e.g. a hosted API, or a
    heavier local model once a GPU is available) means adding another
    EmbeddingProvider subclass and changing EMBEDDING_MODEL_ID / the
    factory below — callers never change.
    """

    def __init__(self, model_id: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_id)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        _provider = FastEmbedProvider(settings.embedding_model_id)
    return _provider
