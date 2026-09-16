"""GigaChat's dialect of the OpenAI API.

Measured against the live service before any of this was written:

- `tools` is accepted and silently ignored — the reply comes back as prose
  and the sheet proposal never arrives. `functions` + `function_call` works.
- the call comes back as `message.function_call`, and its `arguments` are an
  object, where the OpenAI API returns a JSON string.
- streaming delivers the whole call in one delta rather than in pieces.

Each of those is a way the assistant loses the ability to edit a sheet
without anything looking broken, so each has a test.
"""

import json
import time

import httpx
import pytest

from app.core import gigachat, llm_provider
from app.core.config import settings


class _Call:
    def __init__(self, name, arguments) -> None:
        self.name = name
        self.arguments = arguments


class _Message:
    def __init__(self, function_call=None, content="") -> None:
        self.function_call = function_call
        self.content = content
        self.tool_calls = None


def test_tools_are_sent_as_functions(monkeypatch) -> None:
    """Sending `tools` to GigaChat loses every sheet edit silently."""
    config = llm_provider.ProviderConfig(
        label="giga", base_url="https://x", api_key="", model="m", dialect="gigachat"
    )
    tool = {"type": "function", "function": {"name": "propose_sheet_change", "parameters": {}}}

    params = llm_provider._tool_params(config, [tool])

    assert "tools" not in params
    assert params["functions"] == [{"name": "propose_sheet_change", "parameters": {}}]
    assert params["function_call"] == "auto"


def test_an_openai_provider_still_gets_tools() -> None:
    config = llm_provider.ProviderConfig(
        label="openai", base_url="https://x", api_key="k", model="m"
    )
    tool = {"type": "function", "function": {"name": "propose_sheet_change"}}

    assert llm_provider._tool_params(config, [tool]) == {"tools": [tool]}


def test_object_arguments_are_read_as_json() -> None:
    """GigaChat sends the arguments as an object; every parser downstream
    reads a string."""
    message = _Message(_Call("propose_sheet_change", {"changes": [{"path": "hp_current"}]}))

    calls = gigachat.calls_in(message)

    assert len(calls) == 1
    name, raw = calls[0]
    assert name == "propose_sheet_change"
    assert json.loads(raw) == {"changes": [{"path": "hp_current"}]}


def test_string_arguments_are_left_alone() -> None:
    message = _Message(_Call("ask_clarifying_question", '{"question": "сколько?"}'))

    assert gigachat.calls_in(message) == [("ask_clarifying_question", '{"question": "сколько?"}')]


def test_a_reply_without_a_call_yields_nothing() -> None:
    assert gigachat.calls_in(_Message(content="просто текст")) == []


def test_a_streamed_call_arriving_whole_is_kept() -> None:
    """Measured: GigaChat sends the entire call in a single delta."""
    store: dict[str, str] = {}

    gigachat.accumulate(store, _Message(_Call("propose_sheet_change", {"changes": []})))

    assert store["name"] == "propose_sheet_change"
    assert json.loads(store["arguments"]) == {"changes": []}


def test_a_streamed_call_arriving_in_pieces_is_joined() -> None:
    """Not what the service does today — but a split call must not silently
    drop the player's sheet edit if it starts doing it."""
    store: dict[str, str] = {}

    gigachat.accumulate(store, _Message(_Call("propose_sheet_change", '{"chan')))
    gigachat.accumulate(store, _Message(_Call(None, 'ges": []}')))

    assert store["name"] == "propose_sheet_change"
    assert json.loads(store["arguments"]) == {"changes": []}


class _Response:
    def __init__(self, status_code, payload) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def _mint(monkeypatch, payload, status=200) -> list[dict]:
    posts: list[dict] = []

    def _fake_post(url, **kwargs):
        posts.append({"url": url, **kwargs})
        return _Response(status, payload)

    monkeypatch.setattr(gigachat.httpx, "post", _fake_post)
    gigachat.forget_tokens()
    return posts


def _token(**overrides) -> str:
    kwargs = {
        "label": "giga",
        "auth_key": "basic-creds",
        "oauth_url": "https://oauth",
        "scope": "GIGACHAT_API_PERS",
        "context": None,
        "timeout": 30.0,
    }
    kwargs.update(overrides)
    return gigachat.access_token(**kwargs)


def test_the_token_is_minted_from_the_credentials(monkeypatch) -> None:
    posts = _mint(monkeypatch, {"access_token": "tok", "expires_at": (time.time() + 1800) * 1000})

    assert _token() == "tok"
    assert posts[0]["headers"]["Authorization"] == "Basic basic-creds"
    assert posts[0]["data"] == {"scope": "GIGACHAT_API_PERS"}


def test_each_mint_carries_its_own_request_id(monkeypatch) -> None:
    """The service rejects a repeated RqUID."""
    posts = _mint(monkeypatch, {"access_token": "tok", "expires_at": (time.time() - 10) * 1000})

    _token()
    _token()

    assert posts[0]["headers"]["RqUID"] != posts[1]["headers"]["RqUID"]


def test_a_live_token_is_reused(monkeypatch) -> None:
    """Minting on every question would add a round trip to every answer."""
    posts = _mint(monkeypatch, {"access_token": "tok", "expires_at": (time.time() + 1800) * 1000})

    _token()
    _token()

    assert len(posts) == 1


def test_a_token_about_to_expire_is_reminted(monkeypatch) -> None:
    """A token that outlives the check but not the request is no token."""
    posts = _mint(monkeypatch, {"access_token": "tok", "expires_at": (time.time() + 10) * 1000})

    _token()
    _token()

    assert len(posts) == 2


def test_refused_credentials_are_reported_not_hidden(monkeypatch) -> None:
    _mint(monkeypatch, {"message": "Unauthorized"}, status=401)

    with pytest.raises(gigachat.GigaChatAuthError):
        _token()


def test_a_missing_expiry_is_treated_as_the_documented_half_hour(monkeypatch) -> None:
    """Not as "never expires": a stale token would fail every later request."""
    _mint(monkeypatch, {"access_token": "tok"})

    _token()

    assert gigachat._tokens["giga"].expires_at <= time.time() + 1801


def test_a_reply_without_a_token_is_refused(monkeypatch) -> None:
    _mint(monkeypatch, {"expires_at": 0})

    with pytest.raises(gigachat.GigaChatAuthError):
        _token()


def test_an_unreachable_token_endpoint_falls_over(monkeypatch) -> None:
    """A network problem minting the token is the same kind of problem as a
    network problem answering — the fallback provider should get its turn."""
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_auth_key", "creds")
    monkeypatch.setattr(settings, "llm_dialect", "gigachat")
    monkeypatch.setattr(settings, "llm_provider_label", "giga")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "cloud-key")
    monkeypatch.setattr(settings, "llm_fallback_provider_label", "cloud")
    llm_provider._clients.clear()
    gigachat.forget_tokens()

    def _boom(url, **kwargs):
        raise httpx.ConnectError("token endpoint unreachable")

    monkeypatch.setattr(gigachat.httpx, "post", _boom)
    monkeypatch.setattr(gigachat, "ssl_context", lambda bundle: None)

    tried: list[str] = []

    def _fake_once(config, messages, tools):
        tried.append(config.label)
        if config.dialect == "gigachat":
            llm_provider._client_for(config)
        return llm_provider.Completion(text="из облака", provider=config.label)

    monkeypatch.setattr(llm_provider, "_complete_once", _fake_once)

    assert llm_provider.complete([{"role": "user", "content": "?"}]).provider == "cloud"
    assert tried == ["giga", "cloud"]


def test_a_hand_built_client_does_not_keep_the_five_second_default(monkeypatch) -> None:
    """Measured: httpx defaults to 5s, the SDK's own client to 600s. Building
    the client ourselves silently swapped one for the other, so the first
    GigaChat answer timed out and fell through to the fallback provider."""
    monkeypatch.setattr(gigachat, "ssl_context", lambda bundle: None)
    config = llm_provider.ProviderConfig(
        label="giga",
        base_url="https://x",
        api_key="",
        model="m",
        dialect="gigachat",
        ca_bundle="certs/whatever.pem",
    )

    client = llm_provider._http_client(config)

    assert client is not None
    assert client.timeout.read == settings.llm_timeout_seconds
    assert settings.llm_timeout_seconds >= 60


def test_an_ordinary_provider_keeps_the_sdk_client() -> None:
    """Handing it a bundle would replace its trust store, not extend it."""
    config = llm_provider.ProviderConfig(
        label="openai", base_url="https://x", api_key="k", model="m"
    )

    assert llm_provider._http_client(config) is None


def test_a_token_provider_counts_as_configured() -> None:
    """The chain used to be filtered on api_key alone, which would drop a
    GigaChat provider on the floor — it has credentials, not a key."""
    config = llm_provider.ProviderConfig(
        label="giga", base_url="https://x", api_key="", model="m", auth_key="creds"
    )

    assert config.configured
    assert not llm_provider.ProviderConfig(
        label="none", base_url="https://x", api_key="", model="m"
    ).configured
