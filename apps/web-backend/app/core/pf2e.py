"""PF2e rule math.

Mirrors apps/web-frontend/src/lib/pf2e.ts. The duplication is deliberate for
now: the frontend needs it to render the sheet live, and the assistant needs
it here to reason about a character without trusting the client or asking the
model to do arithmetic. Both sides are covered by tests stating the same
rules, so a divergence fails a build rather than silently skewing answers.
"""

from typing import Literal

ProficiencyRank = Literal["untrained", "trained", "expert", "master", "legendary"]

_PROFICIENCY_BONUS: dict[str, int] = {
    "untrained": 0,
    "trained": 2,
    "expert": 4,
    "master": 6,
    "legendary": 8,
}

RANK_LABEL: dict[str, str] = {
    "untrained": "нетренирован",
    "trained": "тренирован",
    "expert": "эксперт",
    "master": "мастер",
    "legendary": "легенда",
}

ABILITY_LABEL: dict[str, str] = {
    "str": "СИЛ",
    "dex": "ЛОВ",
    "con": "ТЕЛ",
    "int": "ИНТ",
    "wis": "МДР",
    "cha": "ХАР",
}

SAVES: list[tuple[str, str, str]] = [
    ("fortitude", "Стойкость", "con"),
    ("reflex", "Реакция", "dex"),
    ("will", "Воля", "wis"),
]

_ARMOR_PENALIZED = {"acrobatics", "athletics", "stealth", "thievery"}

SKILLS: list[tuple[str, str, str]] = [
    ("acrobatics", "Акробатика", "dex"),
    ("arcana", "Магия", "int"),
    ("athletics", "Атлетика", "str"),
    ("crafting", "Ремесло", "int"),
    ("deception", "Обман", "cha"),
    ("diplomacy", "Дипломатия", "cha"),
    ("intimidation", "Запугивание", "cha"),
    ("medicine", "Медицина", "wis"),
    ("nature", "Природа", "wis"),
    ("occultism", "Оккультизм", "int"),
    ("performance", "Выступление", "cha"),
    ("religion", "Религия", "wis"),
    ("society", "Общество", "int"),
    ("stealth", "Скрытность", "dex"),
    ("survival", "Выживание", "wis"),
    ("thievery", "Воровство", "dex"),
]


def has_armor_penalty(skill_key: str) -> bool:
    return skill_key in _ARMOR_PENALIZED


def proficiency_bonus(rank: str, level: int) -> int:
    """PF2e: untrained adds nothing at all — level only counts once trained."""
    if rank == "untrained":
        return 0
    return level + _PROFICIENCY_BONUS.get(rank, 0)


def stat_total(
    *,
    ability_mod: int,
    level: int,
    rank: str,
    item: int = 0,
    temporary: int = 0,
    base: int = 0,
    armor_penalty: int = 0,
) -> int:
    return (
        base
        + ability_mod
        + proficiency_bonus(rank, level)
        + item
        + temporary
        + armor_penalty
    )


def max_hp(
    *,
    ancestry: int,
    per_level: int,
    con_mod: int,
    level: int,
    item: int = 0,
    other: int = 0,
    penalty: int = 0,
) -> int:
    """PF2e: class HP and Constitution both apply at every level."""
    return ancestry + (per_level + con_mod) * level + item + other - penalty


def format_modifier(value: int) -> str:
    return f"+{value}" if value >= 0 else str(value)
