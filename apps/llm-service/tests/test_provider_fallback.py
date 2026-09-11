"""The fallback exists so a switched-off GPU machine degrades, not breaks."""

import httpx
import pytest
from openai import APIConnectionError, BadRequestError

from app.core import llm_provider
from app.core.config import settings


def _configure(monkeypatch, *, fallback_key: str = "cloud-key") -> None:
    monkeypatch.setattr(settings, "llm_api_key", "local-key")
    monkeypatch.setattr(settings, "llm_provider_label", "local")
    monkeypatch.setattr(settings, "llm_fallback_api_key", fallback_key)
    monkeypatch.setattr(settings, "llm_fallback_provider_label", "cloud")
    llm_provider._clients.clear()


def test_chain_is_primary_then_fallback(monkeypatch) -> None:
    _configure(monkeypatch)

    assert [config.label for config in llm_provider.providers()] == ["local", "cloud"]


def test_no_fallback_listed_without_a_key(monkeypatch) -> None:
    _configure(monkeypatch, fallback_key="")

    assert [config.label for config in llm_provider.providers()] == ["local"]


def test_falls_back_when_the_primary_is_unreachable(monkeypatch) -> None:
    _configure(monkeypatch)
    tried: list[str] = []

    def _fake_once(config, message, tools):
        tried.append(config.label)
        if config.label == "local":
            raise APIConnectionError(request=httpx.Request("POST", "http://localhost:11434"))
        return llm_provider.Completion(text="из облака", provider=config.label)

    monkeypatch.setattr(llm_provider, "_complete_once", _fake_once)

    completion = llm_provider.complete("вопрос")

    assert tried == ["local", "cloud"]
    assert completion.text == "из облака"
    assert completion.provider == "cloud"


def test_primary_answer_is_used_without_touching_the_fallback(monkeypatch) -> None:
    _configure(monkeypatch)
    tried: list[str] = []

    def _fake_once(config, message, tools):
        tried.append(config.label)
        return llm_provider.Completion(text="локально", provider=config.label)

    monkeypatch.setattr(llm_provider, "_complete_once", _fake_once)

    assert llm_provider.complete("вопрос").provider == "local"
    assert tried == ["local"]


def test_a_bad_request_is_not_retried_elsewhere(monkeypatch) -> None:
    """Falling back on a malformed request would hide the bug behind a bill."""
    _configure(monkeypatch)
    tried: list[str] = []

    def _fake_once(config, message, tools):
        tried.append(config.label)
        response = httpx.Response(400, request=httpx.Request("POST", "http://x"))
        raise BadRequestError(message="bad", response=response, body=None)

    monkeypatch.setattr(llm_provider, "_complete_once", _fake_once)

    with pytest.raises(BadRequestError):
        llm_provider.complete("вопрос")
    assert tried == ["local"]


def test_raises_when_every_provider_is_down(monkeypatch) -> None:
    _configure(monkeypatch)

    def _fake_once(config, message, tools):
        raise APIConnectionError(request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(llm_provider, "_complete_once", _fake_once)

    with pytest.raises(APIConnectionError):
        llm_provider.complete("вопрос")


def test_no_configured_provider_is_reported_clearly(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "")
    llm_provider._clients.clear()

    with pytest.raises(llm_provider.LLMNotConfiguredError):
        llm_provider.complete("вопрос")
