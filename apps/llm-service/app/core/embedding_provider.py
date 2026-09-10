from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import settings


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed one or more texts into vectors, in the given order."""


class FastEmbedProvider(EmbeddingProvider):
    """Local, ONNX-based embeddings (fastembed) — the CPU fallback.

    Deliberately not PyTorch/transformers: loading even a small (~420MB)
    transformers model crashed with MemoryError on the low-RAM machine this
    was first built on; fastembed's quantized ONNX runtime has a much lower
    peak memory footprint. Retrieval quality is modest, which is why the
    Ollama backend below is preferred when a GPU is present.
    """

    def __init__(self, model_id: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_id)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embeddings from a local Ollama server, so they run on the GPU.

    Lets us use a genuinely multilingual model (bge-m3) instead of the small
    ONNX one — Russian retrieval on the light model was noticeably weak.
    """

    def __init__(self, model_id: str, base_url: str, timeout: float) -> None:
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        response = httpx.post(
            f"{self._base_url}/api/embed",
            json={"model": self._model_id, "input": texts},
            timeout=self._timeout,
        )
        response.raise_for_status()
        embeddings = response.json()["embeddings"]

        if len(embeddings) != len(texts):
            # Silently short vectors would misalign ids and documents in the
            # vector store, which is far worse than failing the batch.
            raise RuntimeError(
                f"Ollama returned {len(embeddings)} embeddings for {len(texts)} texts"
            )
        return embeddings


_provider: EmbeddingProvider | None = None


def build_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_backend == "ollama":
        return OllamaEmbeddingProvider(
            model_id=settings.embedding_model_id,
            base_url=settings.embedding_base_url,
            timeout=settings.embedding_timeout_seconds,
        )
    return FastEmbedProvider(settings.embedding_model_id)


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        _provider = build_embedding_provider()
    return _provider
