"""Renders a character sheet into the text block sent to the LLM."""

from app.models.character import Character
from app.rulesets.pf2e import rules as pf2e

# Never leaves the backend: the ml-system-design rules forbid sending user PII
# to the model, and these say nothing about the character's rules situation.
_EXCLUDED_SHEET_FIELDS = frozenset({"player_name", "notes"})

_EMPTY_COMPONENTS: dict = {"rank": "untrained", "item": 0, "temporary": 0}


def _components(sheet: dict, key: str) -> dict:
    return (sheet.get("stats") or {}).get(key) or _EMPTY_COMPONENTS


def _ability_mod(character: Character, ability: str) -> int:
    return getattr(character, f"{ability}_mod")


def _stat_line(
    label: str,
    ability: str,
    character: Character,
    components: dict,
    armor_penalty: int = 0,
) -> str:
    total = pf2e.stat_total(
        ability_mod=_ability_mod(character, ability),
        level=character.level,
        rank=components.get("rank", "untrained"),
        item=components.get("item", 0),
        temporary=components.get("temporary", 0),
        armor_penalty=armor_penalty,
    )
    rank_label = pf2e.RANK_LABEL.get(components.get("rank", "untrained"), "нетренирован")
    return (
        f"- {label} ({pf2e.ABILITY_LABEL[ability]}): "
        f"{pf2e.format_modifier(total)} [{rank_label}]"
    )


def build_character_context(character: Character) -> str:
    """A readable snapshot of the sheet, with every modifier already resolved.

    Totals are computed here rather than left to the model: arithmetic is
    exactly what an LLM is worst at, and a wrong skill bonus reads just as
    confidently as a right one.
    """
    sheet = character.sheet_data or {}
    hp = sheet.get("hp") or {}
    armor = sheet.get("armor") or {}
    armor_penalty = armor.get("check_penalty", 0) or 0

    computed_max_hp = pf2e.max_hp(
        ancestry=hp.get("ancestry", 0),
        per_level=hp.get("per_level", 0),
        con_mod=character.con_mod,
        level=character.level,
        item=hp.get("item", 0),
        other=hp.get("other", 0),
        penalty=hp.get("penalty", 0),
    )

    dex_cap = armor.get("dex_cap")
    capped_dex = character.dex_mod if dex_cap is None else min(character.dex_mod, dex_cap)
    ac_components = _components(sheet, "armor_class")
    ac = pf2e.stat_total(
        ability_mod=capped_dex,
        level=character.level,
        base=10,
        rank=ac_components.get("rank", "untrained"),
        item=ac_components.get("item", 0),
        temporary=ac_components.get("temporary", 0),
    )

    lines = [
        f"Персонаж: {character.name}",
        f"Уровень {character.level}"
        + (f", {character.ancestry}" if character.ancestry else "")
        + (f", {character.class_name}" if character.class_name else "")
        + (f", предыстория: {character.background}" if character.background else ""),
        "",
        "Характеристики: "
        + ", ".join(
            f"{pf2e.ABILITY_LABEL[key]} {pf2e.format_modifier(_ability_mod(character, key))}"
            for key in ("str", "dex", "con", "int", "wis", "cha")
        ),
        "",
        f"ХП: {character.hp_current}/{computed_max_hp}"
        + (f" (временных {hp['temporary']})" if hp.get("temporary") else ""),
        f"КБ: {ac}",
        f"Скорость: {character.speed} фт.",
        _stat_line("Восприятие", "wis", character, _components(sheet, "perception")),
        "",
        "Спасброски:",
        *[
            _stat_line(label, ability, character, _components(sheet, key))
            for key, label, ability in pf2e.SAVES
        ],
        "",
        "Навыки:",
        *[
            _stat_line(
                label,
                ability,
                character,
                _components(sheet, key),
                armor_penalty if pf2e.has_armor_penalty(key) else 0,
            )
            for key, label, ability in pf2e.SKILLS
        ],
    ]

    conditions = {key: value for key, value in (sheet.get("conditions") or {}).items() if value}
    if conditions:
        lines += [
            "",
            "Активные состояния: "
            + ", ".join(
                f"{key} {value}" if value > 1 else key for key, value in sorted(conditions.items())
            ),
        ]

    extra_fields = (
        ("senses", "Чувства"),
        ("languages", "Языки"),
        ("resistances", "Сопротивления"),
    )
    for field, label in extra_fields:
        value = sheet.get(field)
        if value and field not in _EXCLUDED_SHEET_FIELDS:
            lines += [f"{label}: {value}"]

    return "\n".join(lines)
