import pytest

from app.core import llm_provider
from app.core.config import settings


def test_get_completion_raises_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(llm_provider, "_client", None)

    with pytest.raises(llm_provider.LLMNotConfiguredError):
        llm_provider.get_completion("hello")
