"""Strips the control markup models sometimes emit as ordinary text.

A model asked to call a tool occasionally writes the tool-call tags into its
prose instead — a reply ending in a bare `</tool_call>` was what prompted
this. The tags mean nothing to the reader and everything about them looks
like a bug, so they are removed before the text leaves the service.

The awkward part is streaming: chunks arrive mid-token, so a tag almost
never lands whole in one piece. TextFilter therefore holds back any trailing
text that could still turn into a marker, and releases it as soon as it
cannot — or at the end of the stream, whichever comes first.
"""

from __future__ import annotations

import re

#: Emitted as text by models whose tool-calling was trained with these tags.
MARKERS: tuple[str, ...] = (
    "<tool_call>",
    "</tool_call>",
    "<tool_response>",
    "</tool_response>",
    "<|im_start|>",
    "<|im_end|>",
    "<|eot_id|>",
)

#: Chat-template special tokens in general: `<|` anything `|>`.
_SPECIAL_TOKEN = re.compile(r"<\|[^|>]*\|>")

#: The only character any marker starts with — nothing else is ever held back.
_OPENS_WITH = "<"


def strip_markup(text: str) -> str:
    """Removes every complete marker from a finished piece of text."""
    for marker in MARKERS:
        text = text.replace(marker, "")
    return _SPECIAL_TOKEN.sub("", text)


def _pending_length(text: str) -> int:
    """How much of the tail could still grow into a marker.

    Only a suffix that is a genuine prefix of some marker is worth holding:
    "СЛ < 15" has a `<`, but `< ` matches nothing, so the text flows on.
    """
    longest = max(len(marker) for marker in MARKERS)
    for size in range(min(longest, len(text)), 0, -1):
        tail = text[-size:]
        if not tail.startswith(_OPENS_WITH):
            continue
        if any(marker.startswith(tail) for marker in MARKERS) or _SPECIAL_TOKEN.match(
            tail + "|>"
        ):
            return size
    return 0


class TextFilter:
    """Incremental twin of strip_markup() for a stream of pieces."""

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, piece: str) -> str:
        """Returns the part of the text that is safe to show now."""
        self._buffer = strip_markup(self._buffer + piece)

        held = _pending_length(self._buffer)
        if held == 0:
            ready, self._buffer = self._buffer, ""
            return ready

        ready = self._buffer[:-held]
        self._buffer = self._buffer[-held:]
        return ready

    def flush(self) -> str:
        """Releases whatever is left — a tag that never completed is just text."""
        ready, self._buffer = strip_markup(self._buffer), ""
        return ready
