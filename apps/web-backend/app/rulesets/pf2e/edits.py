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
    "blinded",
    "clumsy",
    "concealed",
    "confused",
    "controlled",
    "dazzled",
    "deafened",
    "doomed",
    "drained",
    "encumbered",
    "enfeebled",
    "fascinated",
    "fatigued",
    "fleeing",
    "frightened",
    "grabbed",
    "hidden",
    "immobilized",
    "invisible",
    "off_guard",
    "paralyzed",
    "petrified",
    "prone",
    "quickened",
    "restrained",
    "sickened",
    "slowed",
    "stunned",
    "stupefied",
    "unconscious",
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
    """What the model believes the sheet currently holds, and by how much it
    is changing that. Optional, and checked when given — see verify_workings."""
    basis: Any = None
    delta: Any = None


@dataclass(frozen=True)
class ResolvedChange:
    """A proposal that passed validation, with what it would replace."""

    path: str
    value: Any
    reason: str
    label: str
    before: Any
    """True when the model showed its arithmetic and the arithmetic held."""
    verified: bool = False


class ChangeRejected(ValueError):
    """The model proposed something outside what a sheet edit may touch."""


def _as_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ChangeRejected(f"{label}: ожидалось число, пришло {value!r}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ChangeRejected(f"{label}: ожидалось число, пришло {value!r}") from exc


def verify_workings(change: ProposedChange, before: Any, value: int, label: str) -> bool:
    """Checks the model's own arithmetic against the sheet.

    Range checks pass anything plausible: for a character on 40 hit points who
    took 12 damage, both 28 and 25 are numbers within bounds, and only one is
    right. So the model is asked to state what it read (`basis`) and what it
    is applying (`delta`), and both are checked here — against the sheet, and
    against each other.

    Returns whether the change was actually vouched for. Missing workings are
    not an error: a model too small to supply them would otherwise be unable
    to touch the sheet at all, which is how "increase my HP" silently did
    nothing before. The player sees the difference instead.
    """
    if change.basis is None and change.delta is None:
        return False

    if change.basis is not None:
        basis = _as_int(change.basis, f"{label}: исходное значение")
        if basis != before:
            raise ChangeRejected(
                f"{label}: ассистент считал от {basis}, а в листе {before} — "
                "расчёт не по текущему состоянию"
            )

    if change.basis is not None and change.delta is not None:
        basis = _as_int(change.basis, f"{label}: исходное значение")
        delta = _as_int(change.delta, f"{label}: величина изменения")
        if basis + delta != value:
            raise ChangeRejected(
                f"{label}: {basis} и {delta:+d} дают {basis + delta}, "
                f"а предложено {value} — ошибка в расчёте"
            )
        return True

    # A basis that matches is worth something on its own: it proves the model
    # read the sheet rather than imagining it.
    return change.basis is not None


def _resolve_column(character: Character, change: ProposedChange) -> ResolvedChange:
    label, low, high = COLUMN_FIELDS[change.path]
    number = _as_int(change.value, label)
    if not low <= number <= high:
        raise ChangeRejected(f"{label}: {number} вне допустимого диапазона {low}…{high}")
    before = getattr(character, change.path)
    return ResolvedChange(
        path=change.path,
        value=number,
        reason=change.reason,
        label=label,
        before=before,
        verified=verify_workings(change, before, number, label),
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
        before = (sheet.get("conditions") or {}).get(key, 0)
        label = f"Состояние «{key}»"
        return ResolvedChange(
            path=change.path,
            value=number,
            reason=change.reason,
            label=label,
            before=before,
            verified=verify_workings(change, before, number, label),
        )

    if parts == ["sheet_data", "hero_points"]:
        number = _as_int(change.value, "Пункты героизма")
        if not 0 <= number <= 3:
            raise ChangeRejected(f"Пункты героизма: {number} вне 0…3")
        before = sheet.get("hero_points", 0)
        return ResolvedChange(
            path=change.path,
            value=number,
            reason=change.reason,
            label="Пункты героизма",
            before=before,
            verified=verify_workings(change, before, number, "Пункты героизма"),
        )

    if parts[:1] == ["sheet_data"] and len(parts) == 2 and parts[1] in {"dying", "wounded"}:
        label = "При смерти" if parts[1] == "dying" else "Ранение"
        number = _as_int(change.value, label)
        if not 0 <= number <= 4:
            raise ChangeRejected(f"{label}: {number} вне 0…4")
        before = sheet.get(parts[1], 0)
        return ResolvedChange(
            path=change.path,
            value=number,
            reason=change.reason,
            label=label,
            before=before,
            verified=verify_workings(change, before, number, label),
        )

    if parts[:2] == ["sheet_data", "stats"] and len(parts) == 4:
        stat, part = parts[2], parts[3]
        if stat not in _STAT_KEYS:
            raise ChangeRejected(f"Неизвестная характеристика: {stat}")
        if part not in _STAT_PARTS:
            raise ChangeRejected(f"У характеристики нельзя менять «{part}»")
        current = (sheet.get("stats") or {}).get(stat) or {}
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
        label = f"{stat} → {part}"
        # A rank is a word, so there is no arithmetic to vouch for.
        checked = part != "rank" and verify_workings(change, before, value, label)
        return ResolvedChange(
            path=change.path,
            value=value,
            reason=change.reason,
            label=label,
            before=before,
            verified=checked,
        )

    raise ChangeRejected(f"Путь «{change.path}» недоступен для правки")


_SHEET_PREFIX = "sheet_data."


def normalize_path(path: str) -> str:
    """Accepts the near-miss paths models actually produce.

    The sheet reaches the model as a single document, so it reasonably writes
    `sheet_data.hp_current` for what we store as a typed column. The intent is
    unambiguous, so honour it rather than rejecting a correct suggestion on a
    naming technicality — observed with a small model turning "heal me 20"
    into `sheet_data.hp_max`, which was then silently dropped.
    """
    if path.startswith(_SHEET_PREFIX) and path[len(_SHEET_PREFIX) :] in COLUMN_FIELDS:
        return path[len(_SHEET_PREFIX) :]
    return path


def resolve_change(character: Character, change: ProposedChange) -> ResolvedChange:
    path = normalize_path(change.path)
    if path != change.path:
        change = ProposedChange(
            path=path,
            value=change.value,
            reason=change.reason,
            basis=change.basis,
            delta=change.delta,
        )

    if change.path in COLUMN_FIELDS:
        return _resolve_column(character, change)
    if change.path.startswith(_SHEET_PREFIX):
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
