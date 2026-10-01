"""Per-ruleset knowledge the general pipeline looks up instead of knowing.

The pipeline sees a chunk as text plus metadata; what a level or a rank
means belongs to the game system the chunk came from (CLAUDE.md §3). A
ruleset with no entry here simply gets no notes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.rulesets.pf2e.availability import availability_note as _pf2e_note

_NOTES: dict[str, Callable[[dict[str, Any], int | None], str | None]] = {
    "pf2e": _pf2e_note,
}


def availability_note(chunk: dict[str, Any], character_level: int | None) -> str | None:
    """What the found page requires of a character's level, or None."""
    note = _NOTES.get(str(chunk["metadata"].get("ruleset") or ""))
    return note(chunk, character_level) if note else None


__all__ = ["availability_note"]
