from app.models.character import Character
from app.rulesets.pf2e.context import build_character_context


def _character(**overrides) -> Character:
    defaults = dict(
        id=1,
        owner_id=1,
        name="Рэм Байер",
        ancestry="человек",
        background="солдат",
        class_name="воин",
        level=5,
        str_mod=4,
        dex_mod=2,
        con_mod=3,
        int_mod=0,
        wis_mod=1,
        cha_mod=0,
        hp_max=73,
        hp_current=60,
        ac=22,
        speed=25,
        sheet_data={},
    )
    defaults.update(overrides)
    return Character(**defaults)


def test_resolves_skill_totals_so_the_model_never_does_arithmetic() -> None:
    character = _character(
        sheet_data={
            "stats": {"athletics": {"rank": "expert", "item": 1, "temporary": 0}},
            "armor": {"dex_cap": 2, "check_penalty": -2},
        }
    )

    context = build_character_context(character)

    # 4 STR + 9 expert-at-5 + 1 item - 2 armor = 12
    assert "Атлетика (СИЛ): +12 [экспертный]" in context


def test_untrained_skill_shows_only_its_ability_modifier() -> None:
    context = build_character_context(_character())

    assert "Дипломатия (ХАР): +0 [неизученный]" in context


def test_armor_penalty_does_not_touch_skills_it_should_not() -> None:
    character = _character(sheet_data={"armor": {"dex_cap": None, "check_penalty": -2}})

    context = build_character_context(character)

    assert "Дипломатия (ХАР): +0" in context
    assert "Акробатика (ЛВК): +0 [неизученный]" in context


def test_computes_max_hp_from_its_composition() -> None:
    character = _character(
        hp_max=0,
        sheet_data={"hp": {"ancestry": 8, "per_level": 10, "item": 0, "other": 0, "penalty": 0}},
    )

    assert "ХП: 60/73" in build_character_context(character)


def test_caps_dexterity_against_armor_for_ac() -> None:
    character = _character(
        dex_mod=4,
        sheet_data={
            "stats": {"armor_class": {"rank": "expert", "item": 2, "temporary": 0}},
            "armor": {"dex_cap": 1, "check_penalty": 0},
        },
    )

    # 10 + 1 (capped from +4) + 9 expert-at-5 + 2 item = 22
    assert "КБ: 22" in build_character_context(character)


def test_lists_only_active_conditions() -> None:
    character = _character(sheet_data={"conditions": {"frightened": 2, "prone": 1, "clumsy": 0}})

    context = build_character_context(character)

    assert "frightened 2" in context
    assert "prone" in context
    assert "clumsy" not in context


def test_never_sends_player_name_to_the_model() -> None:
    character = _character(sheet_data={"player_name": "Никита", "notes": "личные заметки"})

    context = build_character_context(character)

    assert "Никита" not in context
    assert "личные заметки" not in context
