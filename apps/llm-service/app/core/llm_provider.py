from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI

from app.core.config import settings
from app.core.tools import PROPOSE_SHEET_CHANGE, parse_change_arguments

_log = logging.getLogger(__name__)


class LLMNotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderConfig:
    label: str
    base_url: str
    api_key: str
    model: str


@dataclass
class Completion:
    text: str
    proposed_changes: list[dict[str, Any]] = field(default_factory=list)
    """Which provider actually answered — the fallback is worth surfacing."""
    provider: str = ""


_clients: dict[str, OpenAI] = {}

#: Errors that mean "this provider is unreachable right now", as opposed to
#: "this request is wrong". Only the former is worth retrying elsewhere —
#: falling back on a bad request would just hide the bug behind a second bill.
_FAILOVER_ERRORS = (APIConnectionError, APITimeoutError, InternalServerError)


def providers() -> list[ProviderConfig]:
    """Primary first, then the fallback if one is configured."""
    chain = [
        ProviderConfig(
            label=settings.llm_provider_label,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    ]
    if settings.llm_fallback_api_key and settings.llm_fallback_base_url:
        chain.append(
            ProviderConfig(
                label=settings.llm_fallback_provider_label,
                base_url=settings.llm_fallback_base_url,
                api_key=settings.llm_fallback_api_key,
                model=settings.llm_fallback_model,
            )
        )
    return chain


def _client_for(config: ProviderConfig) -> OpenAI:
    if config.label not in _clients:
        _clients[config.label] = OpenAI(base_url=config.base_url, api_key=config.api_key)
    return _clients[config.label]


def _complete_once(
    config: ProviderConfig, message: str, tools: list[dict[str, Any]] | None
) -> Completion:
    request: dict[str, Any] = {
        "model": config.model,
        "messages": [{"role": "user", "content": message}],
    }
    if tools:
        request["tools"] = tools

    response = _client_for(config).chat.completions.create(**request)
    choice = response.choices[0].message

    changes: list[dict[str, Any]] = []
    for call in getattr(choice, "tool_calls", None) or []:
        if getattr(call.function, "name", None) == PROPOSE_SHEET_CHANGE:
            changes.extend(parse_change_arguments(call.function.arguments))

    return Completion(text=choice.content or "", proposed_changes=changes, provider=config.label)


def complete(message: str, tools: list[dict[str, Any]] | None = None) -> Completion:
    """One turn, falling through the provider chain if a provider is down.

    The local GPU is the primary; when that machine is off, the cloud
    fallback keeps the app usable instead of failing outright.
    """
    chain = [config for config in providers() if config.api_key]
    if not chain:
        raise LLMNotConfiguredError(
            "LLM_API_KEY is not set — add it to .env (see .env.example)."
        )

    last_error: Exception | None = None
    for index, config in enumerate(chain):
        try:
            completion = _complete_once(config, message, tools)
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
    return complete(message).text


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
    config: ProviderConfig, message: str, tools: list[dict[str, Any]] | None
) -> Iterator[str | Completion]:
    """Yields text pieces, then one Completion carrying the assembled result."""
    request: dict[str, Any] = {
        "model": config.model,
        "messages": [{"role": "user", "content": message}],
        "stream": True,
    }
    if tools:
        request["tools"] = tools

    text_parts: list[str] = []
    calls: dict[int, dict[str, str]] = {}

    for chunk in _client_for(config).chat.completions.create(**request):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        piece = getattr(delta, "content", None)
        if piece:
            text_parts.append(piece)
            yield piece
        _accumulate_tool_calls(calls, getattr(delta, "tool_calls", None))

    changes: list[dict[str, Any]] = []
    for call in calls.values():
        if call["name"] == PROPOSE_SHEET_CHANGE:
            changes.extend(parse_change_arguments(call["arguments"]))

    yield Completion(
        text="".join(text_parts), proposed_changes=changes, provider=config.label
    )


def stream(
    message: str, tools: list[dict[str, Any]] | None = None
) -> Iterator[str | Completion]:
    """Streaming twin of complete(), with the same provider fallback.

    Failover only applies before the first token: once text has reached the
    caller, switching providers mid-answer would splice two different replies
    together, which reads worse than an honest error.
    """
    chain = [config for config in providers() if config.api_key]
    if not chain:
        raise LLMNotConfiguredError(
            "LLM_API_KEY is not set — add it to .env (see .env.example)."
        )

    last_error: Exception | None = None
    for index, config in enumerate(chain):
        started = False
        try:
            for item in _stream_once(config, message, tools):
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
