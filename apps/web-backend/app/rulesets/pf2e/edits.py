"""What the assistant is allowed to change on a PF2e sheet, and how.

The model never writes to the sheet directly. It proposes changes by path;
this module decides whether a path is writable at all, whether the value is
sane, and renders a before/after line the player confirms. Anything not
listed here is refused — a sheet is the player's, and a model that can
quietly rewrite arbitrary fields is worse than one that cannot write at all.
"""

import difflib
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

#: Free text that belongs to the player rather than to the rules. Nothing
#: here can distort a rule: it is their own fiction, a wrong value is visible
#: at a glance, and fixing it is one click. Opened so the assistant can fill
#: a sheet, not just adjust the numbers on one already filled.
TEXT_COLUMNS: dict[str, str] = {
    "name": "Имя",
    "ancestry": "Происхождение",
    "background": "Предыстория",
    "class_name": "Класс",
}

#: The same, one level inside the sheet document.
SHEET_TEXT_FIELDS: dict[str, str] = {
    "player_name": "Имя игрока",
    "heritage": "Наследие",
    "size": "Размер",
    "alignment": "Мировоззрение",
    "traits": "Черты",
    "deity": "Божество",
    "languages": "Языки",
    "senses": "Чувства",
    "speed_notes": "Заметки о скорости",
    "saves_notes": "Заметки об испытаниях",
    "resistances": "Сопротивления",
    "notes": "Заметки",
}

#: Of the fields above, the ones the player writes rather than the rules
#: decide: the assistant may add to them but not replace them.
_PLAYERS_PROSE_FIELDS = {"notes", "speed_notes", "saves_notes"}

#: sheet_data.<group>.<key> — the prose sections of the printed sheet.
SHEET_TEXT_GROUPS: dict[str, tuple[str, dict[str, str]]] = {
    "bio": (
        "Биография",
        {
            "ethnicity": "Народность",
            "nationality": "Гражданство",
            "birthplace": "Место рождения",
            "age": "Возраст",
            "gender": "Пол",
            "height": "Рост",
            "weight": "Вес",
            "appearance": "Внешность",
        },
    ),
    "personality": (
        "Характер",
        {
            "attitude": "Нрав",
            "beliefs": "Убеждения",
            "likes": "Нравится",
            "dislikes": "Не нравится",
            "catchphrases": "Присказки",
        },
    ),
    "campaign": (
        "Кампания",
        {
            "notes": "Заметки",
            "allies": "Союзники",
            "enemies": "Враги",
            "organizations": "Организации",
        },
    ),
}

#: Lists of cards — items, feats, spells. Each is replaced wholesale rather
#: than appended to: a proposal the player can read as "this is the list
#: afterwards" is one they can judge, where "add one somewhere" is not.
CARD_FIELDS: dict[str, str] = {
    "ancestry_feats": "Черты происхождения",
    "skill_feats": "Черты навыков",
    "general_feats": "Общие черты",
    "class_feats": "Черты класса",
    "bonus_feats": "Дополнительные черты",
    "inventory.worn": "Надето",
    "inventory.ready": "В руках",
    "inventory.other": "Прочее снаряжение",
    "spells": "Заклинания",
    "focus_spells": "Фокусные заклинания",
    "innate_spells": "Врождённые заклинания",
}

#: Stamped on any card the assistant filled in. Until the pf2.ru catalogue is
#: indexed the model writes these from memory, and a sheet must not present
#: that as if it came out of a book.
ASSISTANT_SOURCE = "со слов ассистента"

MAX_TEXT_CHARS = 2000
MAX_CARDS = 60
MAX_CARD_KEYS = 24

#: Which part of the sheet a path belongs to. Filling a sheet produces dozens
#: of changes at once, and forty diff lines with one button underneath is a
#: confirmation nobody reads — grouped, the player can take it a part at a time.
_SECTIONS: tuple[tuple[str, str], ...] = (
    ("sheet_data.bio.", "Биография"),
    ("sheet_data.personality.", "Характер"),
    ("sheet_data.campaign.", "Кампания"),
    ("sheet_data.inventory.", "Снаряжение"),
    ("sheet_data.stats.", "Навыки и испытания"),
    ("sheet_data.conditions.", "Состояния"),
)

_SECTION_BY_FIELD: dict[str, str] = {
    **{key: "Личность" for key in TEXT_COLUMNS},
    **{f"sheet_data.{key}": "Личность" for key in SHEET_TEXT_FIELDS},
    **{
        f"sheet_data.{key}": "Черты"
        for key in ("ancestry_feats", "skill_feats", "general_feats", "class_feats", "bonus_feats")
    },
    **{f"sheet_data.{key}": "Магия" for key in ("spells", "focus_spells", "innate_spells")},
    "sheet_data.hero_points": "Состояния",
    "sheet_data.dying": "Состояния",
    "sheet_data.wounded": "Состояния",
}


def section_for(path: str) -> str:
    """Groups a change under a heading the player recognises from the sheet."""
    for prefix, label in _SECTIONS:
        if path.startswith(prefix):
            return label
    return _SECTION_BY_FIELD.get(path, "Основное")


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

#: The book's abbreviations, as models write them in a saves folder.
_STAT_SHORT_NAMES = {"fort": "fortitude", "ref": "reflex"}

#: Every path a proposal may write, for suggesting the nearest one when a
#: proposal misses. The model reads the suggestion back on its retry.
_EDITABLE_PATHS: tuple[str, ...] = (
    *COLUMN_FIELDS,
    *TEXT_COLUMNS,
    *(f"sheet_data.{key}" for key in SHEET_TEXT_FIELDS),
    *(
        f"sheet_data.{group}.{key}"
        for group, (_, keys) in SHEET_TEXT_GROUPS.items()
        for key in keys
    ),
    *(f"sheet_data.{key}" for key in CARD_FIELDS),
    "sheet_data.hero_points",
    "sheet_data.dying",
    "sheet_data.wounded",
    *(f"sheet_data.ability_scores.{key}" for key in rules.ABILITY_LABEL),
    *(f"sheet_data.stats.{stat}.{part}" for stat in sorted(_STAT_KEYS) for part in _STAT_PARTS),
    *(f"sheet_data.conditions.{key}" for key in sorted(_CONDITION_KEYS)),
)


def _hint(path: str) -> str:
    """Where a refused proposal should have gone, when that can be told.

    Live sheet builds missed in the same few ways: a whole prose section
    written as one value, an ability filed as a skill, a card list under an
    invented folder. A retry told only "unavailable" guessed again and missed
    again; told the real path, it can fix the proposal.
    """
    if path in _EDITABLE_PATHS:
        # The path exists; what was refused is the value, and its own reason
        # already says what is wrong with it.
        return ""
    parts = path.split(".")
    lowered = path.lower()
    # Spelled out rather than left to string similarity: measured on the
    # paths seen live, the nearest match for sheet_data.feats.class was
    # stats.class_dc and for sheet_data.cantrips was sheet_data.traits.
    if "feat" in lowered:
        lists = ", ".join(f"sheet_data.{key}" for key in CARD_FIELDS if key.endswith("_feats"))
        return f"черты пишутся в один из списков: {lists}"
    if "spell" in lowered or "cantrip" in lowered:
        lists = ", ".join(f"sheet_data.{key}" for key in CARD_FIELDS if key.endswith("spells"))
        return f"заклинания пишутся в один из списков: {lists}"
    if path == "sheet_data.conditions":
        return (
            "это раздел; указывай числом только те состояния, что действуют на "
            "персонажа: sheet_data.conditions.<frightened|sickened|…>; у нового "
            "персонажа их обычно нет, и тогда ничего присылать не нужно"
        )
    if len(parts) == 2 and parts[0] == "sheet_data" and parts[1] in SHEET_TEXT_GROUPS:
        keys = "|".join(SHEET_TEXT_GROUPS[parts[1]][1])
        return f"это раздел, укажи поле: sheet_data.{parts[1]}.<{keys}>"
    named_stat = next(
        (
            _STAT_SHORT_NAMES.get(part, part)
            for part in parts[1:]
            if _STAT_SHORT_NAMES.get(part, part) in _STAT_KEYS
        ),
        None,
    )
    if parts[0] == "sheet_data" and named_stat and parts[1] != "stats":
        return (
            f"навыки и испытания пишутся так: sheet_data.stats.{named_stat}.<rank|item|temporary>"
        )
    if len(parts) >= 3 and parts[:2] == ["sheet_data", "stats"]:
        if parts[2] in rules.ABILITY_LABEL:
            return (
                f"{parts[2]} — характеристика, а не навык: значение пишется в "
                f"sheet_data.ability_scores.{parts[2]}, модификатор — в {parts[2]}_mod"
            )
        if parts[2] not in _STAT_KEYS:
            return "в sheet_data.stats есть только: " + ", ".join(sorted(_STAT_KEYS))
        return "у навыка меняются только rank, item и temporary; модификатор считает программа"
    close = difflib.get_close_matches(path, _EDITABLE_PATHS, n=1, cutoff=0.8)
    return f"возможно, имелось в виду «{close[0]}»" if close else ""


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
    """Which part of the sheet this belongs to, for grouping the diff."""
    section: str = "Основное"


class ChangeRejected(ValueError):
    """The model proposed something outside what a sheet edit may touch."""


def _as_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ChangeRejected(f"{label}: ожидалось число, пришло {value!r}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ChangeRejected(f"{label}: ожидалось число, пришло {value!r}") from exc


def _as_text(value: Any, label: str) -> str:
    if value is None:
        return ""
    # Plainly plural fields — languages, senses, resistances — are one line
    # here but a list to the model, which offered ["Common", "Elven"] and was
    # told it had filled the field wrongly. Joining words is faithful; joining
    # anything richer would turn a wrong shape into plausible junk.
    if isinstance(value, list) and all(isinstance(item, (str, int, float)) for item in value):
        value = ", ".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ChangeRejected(f"{label}: ожидался текст, пришло {type(value).__name__}")
    text = str(value).strip()
    if len(text) > MAX_TEXT_CHARS:
        raise ChangeRejected(f"{label}: длиннее {MAX_TEXT_CHARS} символов")
    return text


def _clean_card(raw: Any, label: str, index: int) -> dict[str, Any]:
    """One card, reduced to what a card can safely be.

    Only flat scalar fields survive: a card is a stat block, and anything
    nested arriving here is the model improvising a shape the sheet cannot
    render. The source is stamped rather than trusted — see ASSISTANT_SOURCE.
    """
    if not isinstance(raw, dict):
        raise ChangeRejected(f"{label}: элемент {index + 1} — не карточка")

    name = _as_text(raw.get("name"), f"{label}: название")
    if not name:
        raise ChangeRejected(f"{label}: у элемента {index + 1} нет названия")

    card: dict[str, Any] = {}
    for key, value in list(raw.items())[:MAX_CARD_KEYS]:
        if not isinstance(key, str):
            continue
        if isinstance(value, bool) or isinstance(value, (int, float)):
            card[key] = value
        elif value is None or isinstance(value, str):
            card[key] = _as_text(value, f"{label}: {key}")
        elif isinstance(value, list) and all(
            isinstance(item, (str, int, float)) and not isinstance(item, bool) for item in value
        ):
            # A card's plural fields — traits above all — are one line on the
            # sheet and a list to the model, which is how a correctly filled
            # "traits": ["fighter", "flourish"] used to be dropped on the
            # floor without a word. Same reading as _as_text gives the plural
            # text columns.
            card[key] = _as_text(value, f"{label}: {key}")

    card["name"] = name
    # Stamped, not trusted: the catalogue is not indexed yet, so this text
    # came out of the model's memory and the sheet must say so.
    if not str(card.get("source") or "").strip():
        card["source"] = ASSISTANT_SOURCE
    return card


def _resolve_cards(
    character: Character, change: ProposedChange, key: str, label: str
) -> ResolvedChange:
    if not isinstance(change.value, list):
        raise ChangeRejected(f"{label}: ожидался список карточек")
    if len(change.value) > MAX_CARDS:
        raise ChangeRejected(f"{label}: больше {MAX_CARDS} карточек за раз")

    cards = [_clean_card(raw, label, i) for i, raw in enumerate(change.value)]

    sheet = character.sheet_data or {}
    parts = key.split(".")
    before: Any = sheet
    for part in parts:
        before = (before or {}).get(part) if isinstance(before, dict) else None
    count = len(before) if isinstance(before, list) else 0

    return ResolvedChange(
        path=change.path,
        value=cards,
        reason=change.reason,
        label=label,
        # A list of stat blocks is unreadable as a diff; the counts are what
        # the player actually judges, and the cards themselves are on screen.
        before=f"{count} шт.",
        section=section_for(change.path),
    )


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
        section=section_for(change.path),
    )


def _resolve_text_column(character: Character, change: ProposedChange) -> ResolvedChange:
    label = TEXT_COLUMNS[change.path]
    return ResolvedChange(
        path=change.path,
        value=_as_text(change.value, label),
        reason=change.reason,
        label=label,
        before=getattr(character, change.path),
        section=section_for(change.path),
    )


def _squashed(text: str) -> str:
    return " ".join(text.split())


def _resolve_sheet_text(
    character: Character,
    change: ProposedChange,
    keys: list[str],
    label: str,
    players_prose: bool = False,
) -> ResolvedChange:
    current: Any = character.sheet_data or {}
    for key in keys:
        current = current.get(key) if isinstance(current, dict) else None
    before = current or ""
    value = _as_text(change.value, label)
    # Live sheet build, 2026-10-01: the player's backstory in the notes was
    # replaced by a summary of the build, one confirmation among forty. What
    # the player wrote may be added to, never dropped.
    if players_prose and before.strip() and _squashed(before) not in _squashed(value):
        raise ChangeRejected(
            f"{label}: здесь уже есть текст игрока, его нельзя заменить, только "
            "дополнить — пришли прежний текст целиком и добавь своё после него"
        )
    return ResolvedChange(
        path=change.path,
        value=value,
        reason=change.reason,
        label=label,
        before=before,
        section=section_for(change.path),
    )


def _resolve_sheet(character: Character, change: ProposedChange) -> ResolvedChange:
    sheet = character.sheet_data or {}
    parts = change.path.split(".")

    if parts[:2] == ["sheet_data", "conditions"] and len(parts) == 3:
        key = parts[2]
        if key not in _CONDITION_KEYS:
            raise ChangeRejected(f"Неизвестное состояние: {key}")
        if isinstance(change.value, bool) or str(change.value).lower() == "false":
            # Seen live: told the conditions were a section of fields, a
            # sheet build sent all 31 of them as False. Absent is the answer.
            raise ChangeRejected(
                f"Состояние {key}: ожидалось число; если состояния нет — не присылай это поле"
            )
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
            section=section_for(change.path),
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
            section=section_for(change.path),
        )

    if parts[:2] == ["sheet_data", "ability_scores"] and len(parts) == 3:
        ability = parts[2]
        if ability not in rules.ABILITY_LABEL:
            raise ChangeRejected(f"Неизвестная характеристика: {ability}")
        # The sheet shows a score next to every modifier — see the frontend's
        # scoreForModifier — but the model can only ever set the *_mod column
        # unless this path exists, which left every AI-built character
        # showing a mismatch the model had no way to fix.
        label = f"{rules.ABILITY_LABEL[ability]} (значение)"
        number = _as_int(change.value, label)
        if not 1 <= number <= 30:
            raise ChangeRejected(f"{label}: {number} вне допустимого диапазона 1…30")
        before = (sheet.get("ability_scores") or {}).get(ability, 10)
        return ResolvedChange(
            path=change.path,
            value=number,
            reason=change.reason,
            label=label,
            before=before,
            verified=verify_workings(change, before, number, label),
            section=section_for(change.path),
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
            section=section_for(change.path),
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
            section=section_for(change.path),
        )

    if len(parts) == 2 and parts[1] in SHEET_TEXT_FIELDS:
        return _resolve_sheet_text(
            character,
            change,
            [parts[1]],
            SHEET_TEXT_FIELDS[parts[1]],
            players_prose=parts[1] in _PLAYERS_PROSE_FIELDS,
        )

    if len(parts) == 3 and parts[1] in SHEET_TEXT_GROUPS:
        group_label, keys = SHEET_TEXT_GROUPS[parts[1]]
        if parts[2] not in keys:
            raise ChangeRejected(f"{group_label}: неизвестное поле «{parts[2]}»")
        # Biography, personality, campaign: all of it is the player's writing.
        return _resolve_sheet_text(
            character,
            change,
            [parts[1], parts[2]],
            f"{group_label}: {keys[parts[2]]}",
            players_prose=True,
        )

    key = ".".join(parts[1:])
    if key in CARD_FIELDS:
        return _resolve_cards(character, change, key, CARD_FIELDS[key])

    raise ChangeRejected(f"Путь «{change.path}» недоступен для правки")


_SHEET_PREFIX = "sheet_data."

#: Group names a model reaches for instead of the sheet's actual "stats" —
#: observed live: a build request wrote sheet_data.skills.acrobatics.rank
#: and sheet_data.saving_throws.fortitude.rank, both readable intent, both
#: rejected on the name of a folder that does not exist. "stats" itself is
#: here too: it is the right name, just paired with a capitalised skill
#: (sheet_data.stats.Acrobatics.rank) that the exact-case 3-part match above
#: does not catch.
_STAT_GROUP_ALIASES = {"skills", "saving_throws", "saves", "stats"}


def normalize_path(path: str) -> str:
    """Accepts the near-miss paths models actually produce.

    The sheet reaches the model as a single document, so it reasonably writes
    `sheet_data.hp_current` for what we store as a typed column. The intent is
    unambiguous, so honour it rather than rejecting a correct suggestion on a
    naming technicality — observed with a small model turning "heal me 20"
    into `sheet_data.hp_max`, which was then silently dropped.
    """
    # Text columns need this as much as numeric ones: a sheet-filling answer
    # wrote sheet_data.ancestry and sheet_data.class_name, and both were
    # refused as "not editable" though the fields are open — which reads to a
    # player as a policy rather than a naming miss.
    bare = path[len(_SHEET_PREFIX) :] if path.startswith(_SHEET_PREFIX) else ""
    if bare and (bare in COLUMN_FIELDS or bare in TEXT_COLUMNS):
        return bare

    parts = path.split(".")

    # "sheet_data.perception.rank" for what is stored at
    # "sheet_data.stats.perception.rank". Observed in a real answer; the stat
    # is named and the part is named, so the intent is not in doubt.
    if (
        len(parts) == 3
        and parts[0] == "sheet_data"
        and parts[1] in _STAT_KEYS
        and parts[2] in _STAT_PARTS
    ):
        return f"sheet_data.stats.{parts[1]}.{parts[2]}"

    # "sheet_data.skills.acrobatics.rank" / "sheet_data.saving_throws.
    # fortitude.rank" / "sheet_data.stats.Acrobatics.rank" for the same
    # place, reached with a folder name that sounds right but is not the one
    # the sheet actually uses, or with the skill capitalised the way the
    # book prints it. The stat has to be real once case-folded, but the part
    # is not checked here on purpose: a model that tried "modifier" instead
    # of "rank" still deserves resolve_change's specific "нельзя менять"
    # answer, not a generic path-not-found.
    if (
        len(parts) == 4
        and parts[0] == "sheet_data"
        and parts[1] in _STAT_GROUP_ALIASES
        and parts[2].lower() in _STAT_KEYS
    ):
        return f"sheet_data.stats.{parts[2].lower()}.{parts[3]}"

    # "sheet_data.stats.dex_mod" for the ability modifier itself, which is a
    # typed column and lives outside sheet_data entirely — the model treated
    # "stats." as a generic prefix for anything characteristic-shaped.
    if (
        len(parts) == 3
        and parts[0] == "sheet_data"
        and parts[1] == "stats"
        and parts[2] in COLUMN_FIELDS
    ):
        return parts[2]

    # "sheet_data.ability_scores.str_mod" for the same column: seen live on a
    # sheet build for all six abilities at once, each refused as an unknown
    # ability — the score and its modifier sit next to each other on the
    # sheet, and the model filed both under the score's folder.
    if (
        len(parts) == 3
        and parts[0] == "sheet_data"
        and parts[1] == "ability_scores"
        and parts[2] in _ABILITY_FIELDS
    ):
        return parts[2]

    # "class_feats" for "sheet_data.class_feats": a card list named without
    # its folder — seen live, after the retry was told the first guess
    # (sheet_data.feats.class) did not exist.
    if path in CARD_FIELDS:
        return f"{_SHEET_PREFIX}{path}"

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
    if change.path in TEXT_COLUMNS:
        return _resolve_text_column(character, change)
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
            reason = str(exc)
            # The model reads these back to correct itself; among forty
            # proposals a reason that does not name its path cannot be acted on.
            if change.path not in reason:
                reason = f"{change.path}: {reason}"
            hint = _hint(normalize_path(change.path))
            rejected.append(f"{reason} — {hint}" if hint else reason)
    return resolved, rejected


def build_update_payload(character: Character, changes: list[ResolvedChange]) -> dict:
    """Turns resolved changes into a PATCH body for the characters endpoint."""
    payload: dict = {}
    sheet: dict | None = None

    for change in changes:
        # Both kinds of typed column, numeric and text: anything not prefixed
        # with sheet_data. is a column, and treating one as a document path
        # would leave nothing to write it into.
        if change.path in COLUMN_FIELDS or change.path in TEXT_COLUMNS:
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
