"""The fallback exists so a switched-off GPU machine degrades, not breaks."""

import httpx
import pytest
from openai import APIConnectionError, BadRequestError, RateLimitError

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

    completion = llm_provider.complete([{"role": "user", "content": "вопрос"}])

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

    assert llm_provider.complete([{"role": "user", "content": "вопрос"}]).provider == "local"
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
        llm_provider.complete([{"role": "user", "content": "вопрос"}])
    assert tried == ["local"]


class _NoChoicesResponse:
    """What a provider returns when it answers with an error, not a completion.

    The free endpoint does this under load: HTTP 200, a body the client
    parses, and `choices` left as None.
    """

    choices = None


class _StubCompletions:
    def __init__(self, response) -> None:
        self._response = response

    def create(self, **_kwargs):
        return self._response


class _StubClient:
    def __init__(self, response) -> None:
        self.chat = type("_Chat", (), {"completions": _StubCompletions(response)})()


def test_a_response_without_choices_fails_over_instead_of_crashing(monkeypatch) -> None:
    """Measured against the running app: this raised TypeError out of
    `response.choices[0]`, which is not a failover error — so the request
    500'd and the configured fallback provider was never tried, in exactly
    the situation it exists for. The player saw "Internal Server Error".
    """
    _configure(monkeypatch)
    tried: list[str] = []

    def _fake_client(config):
        tried.append(config.label)
        if config.label == "local":
            return _StubClient(_NoChoicesResponse())
        return _StubClient(
            type(
                "_Ok",
                (),
                {
                    "choices": [
                        type(
                            "_Choice",
                            (),
                            {
                                "message": type(
                                    "_Message",
                                    (),
                                    {"content": "из облака", "tool_calls": None},
                                )()
                            },
                        )()
                    ]
                },
            )()
        )

    monkeypatch.setattr(llm_provider, "_client_for", _fake_client)

    completion = llm_provider.complete([{"role": "user", "content": "вопрос"}])

    assert tried == ["local", "cloud"]
    assert completion.text == "из облака"
    assert completion.provider == "cloud"


def test_a_rate_limited_provider_hands_over_to_the_fallback(monkeypatch) -> None:
    """Measured on the free endpoint: enough questions in a row and it starts
    answering 429 for minutes. That is "not me, not now" — the case the
    fallback exists for — but it used to surface as an error to the player.
    """
    _configure(monkeypatch)
    tried: list[str] = []

    def _fake_once(config, message, tools):
        tried.append(config.label)
        if config.label == "local":
            response = httpx.Response(429, request=httpx.Request("POST", "http://x"))
            raise RateLimitError(message="slow down", response=response, body=None)
        return llm_provider.Completion(text="из облака", provider=config.label)

    monkeypatch.setattr(llm_provider, "_complete_once", _fake_once)

    assert llm_provider.complete([{"role": "user", "content": "вопрос"}]).provider == "cloud"
    assert tried == ["local", "cloud"]


def test_raises_when_every_provider_is_down(monkeypatch) -> None:
    _configure(monkeypatch)

    def _fake_once(config, message, tools):
        raise APIConnectionError(request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(llm_provider, "_complete_once", _fake_once)

    with pytest.raises(APIConnectionError):
        llm_provider.complete([{"role": "user", "content": "вопрос"}])


def test_no_configured_provider_is_reported_clearly(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "")
    llm_provider._clients.clear()

    with pytest.raises(llm_provider.LLMNotConfiguredError):
        llm_provider.complete([{"role": "user", "content": "вопрос"}])
