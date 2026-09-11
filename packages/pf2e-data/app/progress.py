"""Progress reporting for long crawls.

A full pass takes hours, so silence is not an option: the reader needs to
know it is still moving and roughly when it ends.

Renders differently depending on where it is pointed. On a terminal it
redraws one line in place; into a log file — where carriage returns would
pile into an unreadable smear — it prints a line every so often instead.
"""

from __future__ import annotations

import sys
import time
from typing import TextIO

_BAR_WIDTH = 24
#: Pages between log lines when not drawing to a terminal.
_LOG_EVERY = 25
#: …and a ceiling on silence, because the crawl rate varies by two orders of
#: magnitude: cached pages fly past, throttled ones take fifteen seconds each.
_LOG_SECONDS = 60.0


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}с"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}м {secs:02d}с"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}ч {minutes:02d}м"


def bar(done: int, total: int, width: int = _BAR_WIDTH) -> str:
    if total <= 0:
        return "░" * width
    filled = round(width * min(done, total) / total)
    return "█" * filled + "░" * (width - filled)


class Progress:
    """Tracks one section while also counting toward a whole-run total."""

    def __init__(
        self,
        label: str,
        total: int,
        *,
        stream: TextIO | None = None,
        overall_done: int = 0,
        overall_total: int = 0,
        started_at: float | None = None,
    ) -> None:
        self.label = label
        self.total = total
        self.done = 0
        self.overall_done = overall_done
        self.overall_total = overall_total
        self._stream = stream or sys.stdout
        self._started = started_at or time.monotonic()
        self._interactive = bool(getattr(self._stream, "isatty", lambda: False)())
        self._last_logged = self._started

    def advance(self, by: int = 1) -> None:
        self.done += by
        self.overall_done += by

        if self._interactive:
            self._draw(end="\r")
            return

        now = time.monotonic()
        if self.done % _LOG_EVERY == 0 or now - self._last_logged >= _LOG_SECONDS:
            self._last_logged = now
            self._draw(end="\n")

    def finish(self) -> None:
        self._draw(end="\n")

    def render(self) -> str:
        percent = 100 * self.done / self.total if self.total else 100.0
        parts = [
            f"{self.label:<14}",
            f"[{bar(self.done, self.total)}]",
            f"{self.done:>5}/{self.total:<5}",
            f"{percent:>3.0f}%",
        ]

        elapsed = time.monotonic() - self._started
        if self.overall_done:
            per_page = elapsed / self.overall_done
            parts.append(f"{per_page:.1f}с/стр")
            # Estimate against the whole run, not this section: the point of
            # the number is "when can I stop watching", not "when does feats end".
            remaining = max(self.overall_total - self.overall_done, 0)
            if remaining:
                parts.append(f"осталось ~{format_duration(remaining * per_page)}")

        if self.overall_total:
            parts.append(f"| всего {self.overall_done}/{self.overall_total}")

        return "  ".join(parts)

    def _draw(self, *, end: str) -> None:
        # Pad to overwrite the tail of a previous, longer line.
        self._stream.write(f"{self.render():<110}{end}")
        self._stream.flush()
