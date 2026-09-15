import pytest

from app.core import llm_provider
from app.core.config import settings


def test_get_completion_raises_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "")
    llm_provider._clients.clear()

    with pytest.raises(llm_provider.LLMNotConfiguredError):
        llm_provider.get_completion("hello")


class _FakeDelta:
    def __init__(self, content: str | None) -> None:
        self.content = content
        self.tool_calls = None


class _FakeChunk:
    def __init__(self, content: str | None) -> None:
        self.choices = [type("C", (), {"delta": _FakeDelta(content)})()]


class _FakeCompletions:
    def __init__(self, pieces: list[str]) -> None:
        self._pieces = pieces

    def create(self, **kwargs):
        return iter([_FakeChunk(p) for p in self._pieces])


class _FakeClient:
    def __init__(self, pieces: list[str]) -> None:
        self.chat = type("Chat", (), {"completions": _FakeCompletions(pieces)})()


def test_streaming_does_not_leak_tool_call_markup(monkeypatch) -> None:
    """A reply ending in a bare </tool_call> is what prompted the filter."""
    from app.core import llm_provider

    config = llm_provider.ProviderConfig(label="test", base_url="x", api_key="k", model="m")
    monkeypatch.setattr(
        llm_provider, "_client_for", lambda _: _FakeClient(["Ответ.", "</tool", "_call>"])
    )

    items = list(llm_provider._stream_once(config, [{"role": "user", "content": "q"}], None))
    pieces = [item for item in items if isinstance(item, str)]
    completion = items[-1]

    assert "".join(pieces) == "Ответ."
    assert completion.text == "Ответ."
