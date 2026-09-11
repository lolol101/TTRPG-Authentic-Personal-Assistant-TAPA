from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.core.config import settings

_log = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def model_id(self) -> str:
        """Identifies the vector space, and so which collection to use."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed one or more texts into vectors, in the given order."""


class FastEmbedProvider(EmbeddingProvider):
    """Local, ONNX-based embeddings (fastembed) — the CPU fallback.

    Deliberately not PyTorch/transformers: loading even a small (~420MB)
    transformers model crashed with MemoryError on the low-RAM machine this
    was first built on; fastembed's quantized ONNX runtime has a much lower
    peak memory footprint. Retrieval quality is modest, which is why the
    Ollama backend is preferred when a GPU is present.
    """

    def __init__(self, model_id: str) -> None:
        from fastembed import TextEmbedding

        self._model_id = model_id
        self._model = TextEmbedding(model_name=model_id)

    @property
    def model_id(self) -> str:
        return self._model_id

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embeddings from a local Ollama server, so they run on the GPU.

    Lets us use a genuinely multilingual model (bge-m3) instead of the small
    ONNX one — Russian retrieval on the light model was noticeably weak.
    """

    def __init__(self, model_id: str, base_url: str, timeout: float, use_gpu: bool) -> None:
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._use_gpu = use_gpu

    @property
    def model_id(self) -> str:
        return self._model_id

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        payload: dict = {"model": self._model_id, "input": texts}
        if not self._use_gpu:
            # num_gpu=0 keeps this model in RAM, so it never competes with the
            # generation model for VRAM. See config.embedding_use_gpu.
            payload["options"] = {"num_gpu": 0}

        response = httpx.post(
            f"{self._base_url}/api/embed",
            json=payload,
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


def _build(backend: str, model_id: str) -> EmbeddingProvider:
    if backend == "ollama":
        return OllamaEmbeddingProvider(
            model_id=model_id,
            base_url=settings.embedding_base_url,
            timeout=settings.embedding_timeout_seconds,
            use_gpu=settings.embedding_use_gpu,
        )
    return FastEmbedProvider(model_id)


def build_embedding_provider() -> EmbeddingProvider:
    """Preferred backend, falling back when it cannot be reached.

    The fallback embeds into a different vector space, so its index lives in
    its own collection — see collection_name(). Mixing them would return
    confident nonsense rather than an error.
    """
    primary = _build(settings.embedding_backend, settings.embedding_model_id)
    try:
        primary.embed(["проверка доступности"])
        return primary
    except Exception as exc:  # noqa: BLE001 — any failure means "use the fallback"
        if not settings.embedding_fallback_backend:
            raise
        _log.warning(
            "embedding backend %r unavailable (%s); falling back to %r",
            settings.embedding_backend,
            type(exc).__name__,
            settings.embedding_fallback_backend,
        )

    return _build(settings.embedding_fallback_backend, settings.embedding_fallback_model_id)


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        _provider = build_embedding_provider()
    return _provider
