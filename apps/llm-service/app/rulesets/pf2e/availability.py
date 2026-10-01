"""What a Pathfinder 2e page requires of a character's level.

The level is read from the stat line the Foundry converter writes under a
page's title — "Spell 3 · Traits: …", "Feat 8 · …", "Weapon 0 · …" (see
packages/pf2e-data/app/foundry.py, _header). Only a page's first chunk
carries that line; a continuation gets no note rather than a guessed one.
"""

from __future__ import annotations

import re
from typing import Any

_STAT_LINE = re.compile(r"^(?P<kind>[A-Z][a-z]+) (?P<level>\d+)(?: ·|$)")

_ITEM_KINDS = {
    "Weapon",
    "Armor",
    "Shield",
    "Equipment",
    "Consumable",
    "Treasure",
    "Backpack",
    "Kit",
}


def _stat_line(text: str) -> tuple[str, int] | None:
    # Title, blank line, stat line: anything further down is description.
    for line in text.splitlines()[:3]:
        match = _STAT_LINE.match(line.strip())
        if match:
            return match["kind"], int(match["level"])
    return None


def _reach(required: int, character_level: int | None) -> str:
    if character_level is None:
        return ""
    state = "уже открыт" if character_level >= required else "ещё не открыт"
    return f"; персонажу ({character_level}-й уровень) по уровню {state}"


def _spell(rank: int, traits: set[str], character_level: int | None) -> str:
    if "cantrip" in traits:
        return "заговор: усиливается сам, уровнем персонажа не ограничен"
    if "focus" in traits:
        return "фокусное заклинание: доступ даёт класс или черта, а не круг"
    opens_at = 2 * rank - 1
    return (
        f"заклинание {rank}-го круга: классы-заклинатели получают этот круг "
        f"на {opens_at}-м уровне персонажа" + _reach(opens_at, character_level)
    )


def _item(level: int, character_level: int | None) -> str:
    note = f"предмет {level}-го уровня"
    if character_level is None:
        return note
    relation = "не выше уровня персонажа" if level <= character_level else "выше уровня персонажа"
    return f"{note}: {relation} ({character_level}-й уровень)"


def availability_note(chunk: dict[str, Any], character_level: int | None) -> str | None:
    found = _stat_line(chunk.get("text", ""))
    if found is None:
        return None
    kind, level = found
    traits = {t.strip() for t in str(chunk["metadata"].get("traits") or "").split(",")}

    if kind == "Spell":
        return _spell(level, traits, character_level)
    if kind == "Feat":
        return f"черта {level}-го уровня: берётся с {level}-го уровня персонажа" + _reach(
            level, character_level
        )
    if kind in _ITEM_KINDS:
        return _item(level, character_level)
    return None
