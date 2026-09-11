import pytest

from app.core import embedding_provider as module
from app.core.embedding_provider import OllamaEmbeddingProvider, build_embedding_provider


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_ollama_provider_sends_model_and_texts(monkeypatch) -> None:
    captured: dict = {}

    def _fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse({"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    import httpx

    monkeypatch.setattr(httpx, "post", _fake_post)
    provider = OllamaEmbeddingProvider("bge-m3", "http://localhost:11434", 30.0, use_gpu=True)

    vectors = provider.embed(["первый", "второй"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"] == "http://localhost:11434/api/embed"
    assert captured["json"] == {"model": "bge-m3", "input": ["первый", "второй"]}


def test_ollama_provider_trims_trailing_slash_in_base_url(monkeypatch) -> None:
    captured: dict = {}

    def _fake_post(url, json, timeout):
        captured["url"] = url
        return _FakeResponse({"embeddings": [[0.0]]})

    import httpx

    monkeypatch.setattr(httpx, "post", _fake_post)

    OllamaEmbeddingProvider("bge-m3", "http://localhost:11434/", 30.0, use_gpu=True).embed(
        ["текст"]
    )

    assert captured["url"] == "http://localhost:11434/api/embed"


def test_ollama_provider_rejects_a_short_batch(monkeypatch) -> None:
    """A missing vector would misalign ids and documents in the store."""

    def _fake_post(url, json, timeout):
        return _FakeResponse({"embeddings": [[0.1]]})

    import httpx

    monkeypatch.setattr(httpx, "post", _fake_post)
    provider = OllamaEmbeddingProvider("bge-m3", "http://localhost:11434", 30.0, use_gpu=True)

    with pytest.raises(RuntimeError, match="1 embeddings for 2 texts"):
        provider.embed(["первый", "второй"])


def test_embeddings_are_pinned_to_the_cpu_by_default(monkeypatch) -> None:
    """Sharing the GPU with the generation model makes Ollama evict one for
    the other, and every ask then pays a model reload — measured at ~150s."""
    captured: dict = {}

    def _fake_post(url, json, timeout):
        captured["json"] = json
        return _FakeResponse({"embeddings": [[0.0]]})

    import httpx

    monkeypatch.setattr(httpx, "post", _fake_post)

    OllamaEmbeddingProvider("bge-m3", "http://localhost:11434", 30.0, use_gpu=False).embed(
        ["текст"]
    )

    assert captured["json"]["options"] == {"num_gpu": 0}


def test_no_gpu_option_is_sent_when_the_gpu_is_allowed(monkeypatch) -> None:
    captured: dict = {}

    def _fake_post(url, json, timeout):
        captured["json"] = json
        return _FakeResponse({"embeddings": [[0.0]]})

    import httpx

    monkeypatch.setattr(httpx, "post", _fake_post)

    OllamaEmbeddingProvider("bge-m3", "http://localhost:11434", 30.0, use_gpu=True).embed(
        ["текст"]
    )

    assert "options" not in captured["json"]


def test_backend_is_chosen_by_config(monkeypatch) -> None:
    monkeypatch.setattr(module.settings, "embedding_backend", "ollama")
    monkeypatch.setattr(module.settings, "embedding_model_id", "bge-m3")

    assert isinstance(build_embedding_provider(), OllamaEmbeddingProvider)
