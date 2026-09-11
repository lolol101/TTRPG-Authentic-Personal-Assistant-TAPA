"""What the assistant is allowed to change on a PF2e sheet, and how.

The model never writes to the sheet directly. It proposes changes by path;
this module decides whether a path is writable at all, whether the value is
sane, and renders a before/after line the player confirms. Anything not
listed here is refused — a sheet is the player's, and a model that can
quietly rewrite arbitrary fields is worse than one that cannot write at all.
"""

from dataclasses import dataclass
from typing import Any

from app.models.character import Character
from app.rulesets.pf2e import rules

_ABILITY_FIELDS = {
    f"{key}_mod": f"{label} (модификатор)" for key, label in rules.ABILITY_LABEL.items()
}

#: Typed columns the assistant may set, with the bounds each one accepts.
COLUMN_FIELDS: dict[str, tuple[str, int, int]] = {
    "hp_current": ("Текущие ПЗ", -999, 9999),
    "hp_max": ("Максимум ПЗ", 0, 9999),
    "level": ("Уровень", 1, 20),
    "ac": ("Класс брони", 0, 99),
    "speed": ("Скорость", 0, 999),
    **{key: (label, -10, 10) for key, label in _ABILITY_FIELDS.items()},
}

_CONDITION_KEYS = {
    "blinded", "clumsy", "concealed", "confused", "controlled", "dazzled",
    "deafened", "doomed", "drained", "encumbered", "enfeebled", "fascinated",
    "fatigued", "fleeing", "frightened", "grabbed", "hidden", "immobilized",
    "invisible", "off_guard", "paralyzed", "petrified", "prone", "quickened",
    "restrained", "sickened", "slowed", "stunned", "stupefied", "unconscious",
    "wounded",
}

_STAT_KEYS = (
    {key for key, _, _ in rules.SKILLS}
    | {key for key, _, _ in rules.SAVES}
    | {"perception", "armor_class", "class_dc"}
)

_STAT_PARTS = {"rank", "item", "temporary"}

_RANKS = set(rules.RANK_LABEL)


@dataclass(frozen=True)
class ProposedChange:
    path: str
    value: Any
    reason: str = ""


@dataclass(frozen=True)
class ResolvedChange:
    """A proposal that passed validation, with what it would replace."""

    path: str
    value: Any
    reason: str
    label: str
    before: Any


class ChangeRejected(ValueError):
    """The model proposed something outside what a sheet edit may touch."""


def _as_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ChangeRejected(f"{label}: ожидалось число, пришло {value!r}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ChangeRejected(f"{label}: ожидалось число, пришло {value!r}") from exc


def _resolve_column(character: Character, change: ProposedChange) -> ResolvedChange:
    label, low, high = COLUMN_FIELDS[change.path]
    number = _as_int(change.value, label)
    if not low <= number <= high:
        raise ChangeRejected(f"{label}: {number} вне допустимого диапазона {low}…{high}")
    return ResolvedChange(
        path=change.path,
        value=number,
        reason=change.reason,
        label=label,
        before=getattr(character, change.path),
    )


def _resolve_sheet(character: Character, change: ProposedChange) -> ResolvedChange:
    sheet = character.sheet_data or {}
    parts = change.path.split(".")

    if parts[:2] == ["sheet_data", "conditions"] and len(parts) == 3:
        key = parts[2]
        if key not in _CONDITION_KEYS:
            raise ChangeRejected(f"Неизвестное состояние: {key}")
        number = _as_int(change.value, f"Состояние {key}")
        if not 0 <= number <= 4:
            raise ChangeRejected(f"Состояние {key}: значение {number} вне 0…4")
        return ResolvedChange(
            path=change.path,
            value=number,
            reason=change.reason,
            label=f"Состояние «{key}»",
            before=(sheet.get("conditions") or {}).get(key, 0),
        )

    if parts == ["sheet_data", "hero_points"]:
        number = _as_int(change.value, "Пункты героизма")
        if not 0 <= number <= 3:
            raise ChangeRejected(f"Пункты героизма: {number} вне 0…3")
        return ResolvedChange(
            path=change.path,
            value=number,
            reason=change.reason,
            label="Пункты героизма",
            before=sheet.get("hero_points", 0),
        )

    if parts[:1] == ["sheet_data"] and len(parts) == 2 and parts[1] in {"dying", "wounded"}:
        label = "При смерти" if parts[1] == "dying" else "Ранение"
        number = _as_int(change.value, label)
        if not 0 <= number <= 4:
            raise ChangeRejected(f"{label}: {number} вне 0…4")
        return ResolvedChange(
            path=change.path,
            value=number,
            reason=change.reason,
            label=label,
            before=sheet.get(parts[1], 0),
        )

    if parts[:2] == ["sheet_data", "stats"] and len(parts) == 4:
        stat, part = parts[2], parts[3]
        if stat not in _STAT_KEYS:
            raise ChangeRejected(f"Неизвестная характеристика: {stat}")
        if part not in _STAT_PARTS:
            raise ChangeRejected(f"У характеристики нельзя менять «{part}»")
        current = ((sheet.get("stats") or {}).get(stat) or {})
        if part == "rank":
            if change.value not in _RANKS:
                raise ChangeRejected(f"Неизвестное умение: {change.value!r}")
            value: Any = change.value
            before: Any = current.get("rank", "untrained")
        else:
            value = _as_int(change.value, f"{stat}.{part}")
            if not -10 <= value <= 10:
                raise ChangeRejected(f"{stat}.{part}: {value} вне -10…10")
            before = current.get(part, 0)
        return ResolvedChange(
            path=change.path,
            value=value,
            reason=change.reason,
            label=f"{stat} → {part}",
            before=before,
        )

    raise ChangeRejected(f"Путь «{change.path}» недоступен для правки")


def resolve_change(character: Character, change: ProposedChange) -> ResolvedChange:
    if change.path in COLUMN_FIELDS:
        return _resolve_column(character, change)
    if change.path.startswith("sheet_data."):
        return _resolve_sheet(character, change)
    raise ChangeRejected(f"Путь «{change.path}» недоступен для правки")


def resolve_changes(
    character: Character, changes: list[ProposedChange]
) -> tuple[list[ResolvedChange], list[str]]:
    """Validates each proposal independently.

    One bad path must not throw away the rest: the player still gets to
    apply the sound suggestions, and sees why the others were dropped.
    """
    resolved: list[ResolvedChange] = []
    rejected: list[str] = []
    for change in changes:
        try:
            resolved.append(resolve_change(character, change))
        except ChangeRejected as exc:
            rejected.append(str(exc))
    return resolved, rejected


def build_update_payload(character: Character, changes: list[ResolvedChange]) -> dict:
    """Turns resolved changes into a PATCH body for the characters endpoint."""
    payload: dict = {}
    sheet: dict | None = None

    for change in changes:
        if change.path in COLUMN_FIELDS:
            payload[change.path] = change.value
            continue

        if sheet is None:
            # Copied once: the model's proposal must not mutate the stored
            # sheet before the player has confirmed anything.
            sheet = _deep_copy(character.sheet_data or {})

        parts = change.path.split(".")[1:]
        target = sheet
        for part in parts[:-1]:
            nested = target.get(part)
            if not isinstance(nested, dict):
                nested = {}
                target[part] = nested
            target = nested
        target[parts[-1]] = change.value

    if sheet is not None:
        payload["sheet_data"] = sheet
    return payload


def _deep_copy(value: dict) -> dict:
    import copy

    return copy.deepcopy(value)
