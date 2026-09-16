"""GigaChat speaks a dialect of the OpenAI API, not the API itself.

Three differences, each forced on us by the service and each fatal if
ignored:

**TLS.** Both endpoints are signed by the Russian state CA, which no ordinary
trust store carries, and the server asks the client to renegotiate mid-
connection — which OpenSSL 3 refuses by default. Without both fixes the
connection does not fail cleanly, it hangs until the timeout.

**Auth.** Not a static key: Basic credentials are exchanged for an access
token that lives about half an hour, so the token has to be reminted while
the service runs.

**Tools.** `tools` is accepted and silently ignored — the model answers in
prose and the proposal never arrives. It calls functions only when they are
sent as `functions` + `function_call`, and it answers with a single
`message.function_call` whose arguments are an object, where the OpenAI API
returns a JSON string.

Everything else — the request shape, streaming, the response envelope — is
close enough that the OpenAI SDK drives it unchanged.
"""

from __future__ import annotations

import json
import logging
import ssl
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

DIALECT = "gigachat"

#: Reminted this long before the token actually expires, so a request that
#: starts just under the wire does not finish just over it.
_REFRESH_MARGIN_SECONDS = 60.0

_log = logging.getLogger(__name__)


class GigaChatAuthError(RuntimeError):
    """The credentials were refused, or the token endpoint answered with
    something unusable.

    Deliberately not a failover error: an endpoint that cannot be reached is
    the fallback provider's cue, but credentials that are simply wrong should
    be seen and fixed, not quietly routed around.
    """


def ssl_context(ca_bundle: str) -> ssl.SSLContext:
    """Trust for GigaChat alone — never installed system-wide.

    OP_LEGACY_SERVER_CONNECT is what makes the handshake complete: the
    endpoint renegotiates mid-connection, and OpenSSL 3 drops such peers
    unless told otherwise. curl on Windows hides this because Schannel
    allows it; Python does not.
    """
    context = ssl.create_default_context(cafile=ca_bundle)
    context.options |= ssl.OP_LEGACY_SERVER_CONNECT
    return context


@dataclass
class _Token:
    value: str
    expires_at: float


_tokens: dict[str, _Token] = {}


def forget_tokens() -> None:
    """Drops every cached token — for tests and for a credentials change."""
    _tokens.clear()


def access_token(
    *,
    label: str,
    auth_key: str,
    oauth_url: str,
    scope: str,
    context: ssl.SSLContext,
    timeout: float,
) -> str:
    """A live access token for this provider, reminted when it is about to
    expire. Cached per provider: minting on every question would double the
    latency of every answer for nothing."""
    cached = _tokens.get(label)
    if cached and cached.expires_at - _REFRESH_MARGIN_SECONDS > time.time():
        return cached.value

    response = httpx.post(
        oauth_url,
        verify=context,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            # The service requires a fresh id per request and rejects repeats.
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {auth_key}",
        },
        data={"scope": scope},
        timeout=timeout,
    )
    if response.status_code != httpx.codes.OK:
        raise GigaChatAuthError(
            f"GigaChat отказал в токене: HTTP {response.status_code} {response.text[:200]}"
        )

    payload = response.json()
    token = str(payload.get("access_token") or "")
    if not token:
        raise GigaChatAuthError("GigaChat вернул ответ без access_token")

    # expires_at is milliseconds since the epoch; a missing one is treated as
    # the documented half hour rather than as "never expires".
    expires_at = float(payload.get("expires_at") or 0) / 1000 or time.time() + 1800
    _tokens[label] = _Token(value=token, expires_at=expires_at)
    _log.info(
        "GigaChat token for %r minted, valid for %.0f min", label, (expires_at - time.time()) / 60
    )
    return token


def function_params(tools: list[dict[str, Any]]) -> dict[str, Any]:
    """The same tools in the shape GigaChat actually reads."""
    return {
        "functions": [tool["function"] for tool in tools if "function" in tool],
        "function_call": "auto",
    }


def _arguments_as_text(arguments: Any) -> str:
    """Our parsers read a JSON string; GigaChat sends the object itself."""
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments, ensure_ascii=False)


def calls_in(message: Any) -> list[tuple[str, str]]:
    """(name, arguments) pairs from a GigaChat reply — at most one."""
    call = getattr(message, "function_call", None)
    name = getattr(call, "name", None) if call is not None else None
    if not name:
        return []
    return [(str(name), _arguments_as_text(getattr(call, "arguments", None)))]


def accumulate(store: dict[str, str], delta: Any) -> None:
    """Collects a streamed function call, which may arrive in pieces.

    Mirrors the OpenAI accumulator: name once, arguments appended. GigaChat
    has been seen to send the whole call in one delta, but a service that
    splits it later must not silently lose the proposal.
    """
    call = getattr(delta, "function_call", None)
    if call is None:
        return
    name = getattr(call, "name", None)
    if name:
        store["name"] = str(name)
    arguments = getattr(call, "arguments", None)
    if arguments is None:
        return
    if isinstance(arguments, str):
        store["arguments"] = store.get("arguments", "") + arguments
    else:
        # An object arrives whole, so it replaces rather than appends.
        store["arguments"] = _arguments_as_text(arguments)


__all__ = [
    "DIALECT",
    "GigaChatAuthError",
    "accumulate",
    "access_token",
    "calls_in",
    "forget_tokens",
    "function_params",
    "ssl_context",
]
