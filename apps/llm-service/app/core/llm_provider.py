from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI

from app.core import gigachat
from app.core.config import settings
from app.core.text_filter import TextFilter, strip_markup
from app.core.tools import (
    ASK_CLARIFICATION,
    PROPOSE_SHEET_CHANGE,
    parse_change_arguments,
    parse_clarification,
)

_log = logging.getLogger(__name__)


class LLMNotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderConfig:
    label: str
    base_url: str
    api_key: str
    model: str
    """Which API this endpoint really speaks — see app.core.gigachat."""
    dialect: str = "openai"
    """Basic credentials exchanged for a short-lived token, where the
    provider works that way instead of taking a static key."""
    auth_key: str = ""
    """Trust bundle for this endpoint alone, when the usual roots do not
    cover it. Empty means the ordinary trust store."""
    ca_bundle: str = ""

    @property
    def configured(self) -> bool:
        """Whether this provider has enough to be called at all."""
        return bool(self.api_key or self.auth_key)


@dataclass
class Completion:
    text: str
    proposed_changes: list[dict[str, Any]] = field(default_factory=list)
    """Which provider actually answered — the fallback is worth surfacing."""
    provider: str = ""
    """Set when the model asked the player something instead of proposing."""
    clarification: dict[str, Any] | None = None
    """Raw arguments of every tool the model called, keyed by tool name.

    Proposals and clarifications are parsed above because the API returns
    them; the retrieval-side tools (planning, query rewriting) are read by
    their own modules, and an absent key is what tells them the model
    declined — which is the ordinary case and must stay cheap."""
    tool_arguments: dict[str, str] = field(default_factory=dict)


_clients: dict[str, OpenAI] = {}

#: Errors that mean "this provider is unreachable right now", as opposed to
#: "this request is wrong". Only the former is worth retrying elsewhere —
#: falling back on a bad request would just hide the bug behind a second bill.
_FAILOVER_ERRORS = (APIConnectionError, APITimeoutError, InternalServerError)


def _ca_bundle_for(dialect: str, configured: str) -> str:
    """A bundle replaces the trust store for that provider outright, so the
    Russian roots are only ever handed to the provider that needs them."""
    if configured:
        return configured
    return settings.gigachat_ca_bundle if dialect == gigachat.DIALECT else ""


def providers() -> list[ProviderConfig]:
    """Primary first, then the fallback if one is configured."""
    chain = [
        ProviderConfig(
            label=settings.llm_provider_label,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            dialect=settings.llm_dialect,
            auth_key=settings.llm_auth_key,
            ca_bundle=_ca_bundle_for(settings.llm_dialect, settings.llm_ca_bundle),
        )
    ]
    fallback = ProviderConfig(
        label=settings.llm_fallback_provider_label,
        base_url=settings.llm_fallback_base_url,
        api_key=settings.llm_fallback_api_key,
        model=settings.llm_fallback_model,
        dialect=settings.llm_fallback_dialect,
        auth_key=settings.llm_fallback_auth_key,
        ca_bundle=_ca_bundle_for(settings.llm_fallback_dialect, settings.llm_fallback_ca_bundle),
    )
    if fallback.configured and fallback.base_url:
        chain.append(fallback)
    return chain


def _http_client(config: ProviderConfig) -> httpx.Client | None:
    """A client that trusts this endpoint, or None for the usual rules.

    The timeout is not decoration: httpx defaults to five seconds, and a
    hand-built client keeps that default instead of the SDK's. Measured, that
    turned every slow first answer into a timeout and a silent fall-through
    to the fallback provider.
    """
    if not config.ca_bundle:
        return None
    return httpx.Client(
        verify=gigachat.ssl_context(config.ca_bundle),
        timeout=settings.llm_timeout_seconds,
    )


def _client_for(config: ProviderConfig) -> OpenAI:
    if config.label not in _clients:
        _clients[config.label] = OpenAI(
            base_url=config.base_url,
            # The SDK refuses to be built without one; a token-based provider
            # gets its real credential below, on every call.
            api_key=config.api_key or "unused",
            http_client=_http_client(config),
        )

    client = _clients[config.label]
    if config.dialect == gigachat.DIALECT:
        # Reminted only when it is about to expire, but re-read every call:
        # the service outlives any single token.
        client.api_key = _token_for(config)
    return client


def _token_for(config: ProviderConfig) -> str:
    """The provider's current token, as a failover error when the token
    endpoint is merely unreachable.

    A network problem here is the same kind of problem as a network problem
    at the chat endpoint — the fallback provider should get its turn. Refused
    credentials are different and are left to surface: falling back would
    hide a misconfiguration behind a second bill.
    """
    try:
        return gigachat.access_token(
            label=config.label,
            auth_key=config.auth_key,
            oauth_url=settings.gigachat_oauth_url,
            scope=settings.gigachat_scope,
            context=gigachat.ssl_context(config.ca_bundle),
            timeout=settings.gigachat_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise APIConnectionError(
            request=httpx.Request("POST", settings.gigachat_oauth_url)
        ) from exc


def _tool_params(config: ProviderConfig, tools: list[dict[str, Any]] | None) -> dict[str, Any]:
    """How to offer tools to this provider.

    GigaChat accepts `tools` and silently ignores it: the model answers in
    prose and the proposal never arrives. It reads `functions` instead.
    """
    if not tools:
        return {}
    if config.dialect == gigachat.DIALECT:
        return gigachat.function_params(tools)
    return {"tools": tools}


def _calls_in(config: ProviderConfig, message: Any) -> list[tuple[str, str]]:
    """(name, raw arguments) for every tool the model called."""
    if config.dialect == gigachat.DIALECT:
        return gigachat.calls_in(message)
    calls = []
    for call in getattr(message, "tool_calls", None) or []:
        name = getattr(call.function, "name", None)
        if name:
            calls.append((str(name), call.function.arguments))
    return calls


def _complete_once(
    config: ProviderConfig, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
) -> Completion:
    request: dict[str, Any] = {"model": config.model, "messages": messages}
    request.update(_tool_params(config, tools))

    client = _client_for(config)
    response = client.chat.completions.create(**request)
    choice = response.choices[0].message

    changes: list[dict[str, Any]] = []
    clarification: dict[str, Any] | None = None
    arguments: dict[str, str] = {}
    for name, raw in _calls_in(config, choice):
        # A model that calls the same tool twice meant it once.
        arguments.setdefault(name, raw)
        if name == PROPOSE_SHEET_CHANGE:
            changes.extend(parse_change_arguments(raw))
        elif name == ASK_CLARIFICATION and clarification is None:
            clarification = parse_clarification(raw)

    return Completion(
        text=strip_markup(choice.content or ""),
        proposed_changes=changes,
        provider=config.label,
        clarification=clarification,
        tool_arguments=arguments,
    )


def complete(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
) -> Completion:
    """One turn, falling through the provider chain if a provider is down.

    The local GPU is the primary; when that machine is off, the cloud
    fallback keeps the app usable instead of failing outright.
    """
    chain = [config for config in providers() if config.configured]
    if not chain:
        raise LLMNotConfiguredError("LLM_API_KEY is not set — add it to .env (see .env.example).")

    last_error: Exception | None = None
    for index, config in enumerate(chain):
        try:
            completion = _complete_once(config, messages, tools)
        except _FAILOVER_ERRORS as exc:
            last_error = exc
            remaining = len(chain) - index - 1
            _log.warning(
                "provider %r unavailable (%s); %s",
                config.label,
                type(exc).__name__,
                f"falling back, {remaining} left" if remaining else "no fallback left",
            )
            continue

        if index > 0:
            _log.info("answered by fallback provider %r", config.label)
        return completion

    raise last_error if last_error else LLMNotConfiguredError("no LLM provider available")


def get_completion(message: str) -> str:
    """Send a single user message to the configured LLM and return its reply."""
    return complete([{"role": "user", "content": message}]).text


def _accumulate_tool_calls(store: dict[int, dict[str, str]], deltas: Any) -> None:
    """Reassembles tool calls, which arrive split across chunks like text does."""
    for delta in deltas or []:
        slot = store.setdefault(delta.index, {"name": "", "arguments": ""})
        function = getattr(delta, "function", None)
        if function is None:
            continue
        if getattr(function, "name", None):
            slot["name"] = function.name
        if getattr(function, "arguments", None):
            slot["arguments"] += function.arguments


def _stream_once(
    config: ProviderConfig, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
) -> Iterator[str | Completion]:
    """Yields text pieces, then one Completion carrying the assembled result."""
    request: dict[str, Any] = {"model": config.model, "messages": messages, "stream": True}
    request.update(_tool_params(config, tools))

    text_parts: list[str] = []
    calls: dict[int, dict[str, str]] = {}
    giga_call: dict[str, str] = {}
    # Models occasionally write their tool-call tags into the prose. Filtered
    # here rather than at the edge so the assembled text is clean too.
    clean = TextFilter()

    client = _client_for(config)
    for chunk in client.chat.completions.create(**request):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        piece = getattr(delta, "content", None)
        if piece:
            ready = clean.feed(piece)
            if ready:
                text_parts.append(ready)
                yield ready
        if config.dialect == gigachat.DIALECT:
            gigachat.accumulate(giga_call, delta)
        else:
            _accumulate_tool_calls(calls, getattr(delta, "tool_calls", None))

    if giga_call.get("name"):
        calls[0] = {"name": giga_call["name"], "arguments": giga_call.get("arguments", "")}

    trailing = clean.flush()
    if trailing:
        text_parts.append(trailing)
        yield trailing

    changes: list[dict[str, Any]] = []
    clarification: dict[str, Any] | None = None
    arguments: dict[str, str] = {}
    for call in calls.values():
        if not call["name"]:
            continue
        arguments.setdefault(call["name"], call["arguments"])
        if call["name"] == PROPOSE_SHEET_CHANGE:
            changes.extend(parse_change_arguments(call["arguments"]))
        elif call["name"] == ASK_CLARIFICATION and clarification is None:
            clarification = parse_clarification(call["arguments"])

    yield Completion(
        text="".join(text_parts),
        proposed_changes=changes,
        provider=config.label,
        clarification=clarification,
        tool_arguments=arguments,
    )


def stream(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
) -> Iterator[str | Completion]:
    """Streaming twin of complete(), with the same provider fallback.

    Failover only applies before the first token: once text has reached the
    caller, switching providers mid-answer would splice two different replies
    together, which reads worse than an honest error.
    """
    chain = [config for config in providers() if config.configured]
    if not chain:
        raise LLMNotConfiguredError("LLM_API_KEY is not set — add it to .env (see .env.example).")

    last_error: Exception | None = None
    for index, config in enumerate(chain):
        started = False
        try:
            for item in _stream_once(config, messages, tools):
                started = True
                yield item
        except _FAILOVER_ERRORS as exc:
            if started:
                raise
            last_error = exc
            remaining = len(chain) - index - 1
            _log.warning(
                "provider %r unavailable (%s); %s",
                config.label,
                type(exc).__name__,
                f"falling back, {remaining} left" if remaining else "no fallback left",
            )
            continue

        if index > 0:
            _log.info("answered by fallback provider %r", config.label)
        return

    raise last_error if last_error else LLMNotConfiguredError("no LLM provider available")
