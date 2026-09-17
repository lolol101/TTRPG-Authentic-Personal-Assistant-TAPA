import pytest

from app.models.character import Character
from app.rulesets.pf2e.edits import (
    ASSISTANT_SOURCE,
    MAX_CARDS,
    ChangeRejected,
    ProposedChange,
    build_update_payload,
    normalize_path,
    resolve_change,
    resolve_changes,
)


def _character(**overrides) -> Character:
    defaults = dict(
        id=1,
        owner_id=1,
        name="Рэм",
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


def test_accepts_a_typed_column_and_reports_the_old_value() -> None:
    resolved = resolve_change(_character(), ProposedChange("hp_current", 45, "получил урон"))

    assert resolved.value == 45
    assert resolved.before == 60
    assert resolved.reason == "получил урон"


def test_refuses_a_column_outside_its_range() -> None:
    with pytest.raises(ChangeRejected, match="вне допустимого диапазона"):
        resolve_change(_character(), ProposedChange("level", 99))


def test_refuses_a_path_that_is_not_on_the_whitelist() -> None:
    """Ownership and identity stay off limits however much else is opened."""
    with pytest.raises(ChangeRejected, match="недоступен для правки"):
        resolve_change(_character(), ProposedChange("owner_id", 2))


def test_refuses_arbitrary_sheet_paths() -> None:
    with pytest.raises(ChangeRejected, match="недоступен для правки"):
        resolve_change(_character(), ProposedChange("sheet_data.whatever_it_invented", 1))


def test_accepts_a_condition_with_its_value() -> None:
    resolved = resolve_change(
        _character(sheet_data={"conditions": {"frightened": 1}}),
        ProposedChange("sheet_data.conditions.frightened", 3),
    )

    assert resolved.value == 3
    assert resolved.before == 1


def test_refuses_an_unknown_condition() -> None:
    with pytest.raises(ChangeRejected, match="Неизвестное состояние"):
        resolve_change(_character(), ProposedChange("sheet_data.conditions.confounded", 1))


def test_refuses_a_condition_value_out_of_range() -> None:
    with pytest.raises(ChangeRejected, match="вне 0…4"):
        resolve_change(_character(), ProposedChange("sheet_data.conditions.frightened", 9))


def test_accepts_a_proficiency_rank() -> None:
    resolved = resolve_change(
        _character(), ProposedChange("sheet_data.stats.athletics.rank", "expert")
    )

    assert resolved.value == "expert"
    assert resolved.before == "untrained"


def test_refuses_an_unknown_rank() -> None:
    with pytest.raises(ChangeRejected, match="Неизвестное умение"):
        resolve_change(_character(), ProposedChange("sheet_data.stats.athletics.rank", "godlike"))


def test_refuses_an_unknown_statistic() -> None:
    with pytest.raises(ChangeRejected, match="Неизвестная характеристика"):
        resolve_change(_character(), ProposedChange("sheet_data.stats.cooking.rank", "expert"))


def test_accepts_an_ability_score_paired_with_its_modifier() -> None:
    """The sheet shows a score next to every modifier — see the frontend's
    scoreForModifier — but until this path existed the model could only ever
    set the *_mod column, so every AI-built character showed a mismatch."""
    resolved = resolve_change(
        _character(sheet_data={"ability_scores": {"str": 10}}),
        ProposedChange("sheet_data.ability_scores.str", 18, "СИЛ 18"),
    )

    assert resolved.value == 18
    assert resolved.before == 10
    assert resolved.section == "Основное"  # groups with str_mod, not sheet_data.*


def test_ability_score_defaults_its_before_value_to_ten() -> None:
    resolved = resolve_change(
        _character(), ProposedChange("sheet_data.ability_scores.dex", 14)
    )

    assert resolved.before == 10


def test_refuses_an_unknown_ability() -> None:
    with pytest.raises(ChangeRejected, match="Неизвестная характеристика"):
        resolve_change(_character(), ProposedChange("sheet_data.ability_scores.luck", 14))


def test_refuses_an_ability_score_out_of_range() -> None:
    with pytest.raises(ChangeRejected, match="вне допустимого диапазона"):
        resolve_change(_character(), ProposedChange("sheet_data.ability_scores.str", 99))


def test_rejects_a_non_numeric_value_for_a_number_field() -> None:
    with pytest.raises(ChangeRejected, match="ожидалось число"):
        resolve_change(_character(), ProposedChange("hp_current", "много"))


def test_one_bad_proposal_does_not_discard_the_good_ones() -> None:
    resolved, rejected = resolve_changes(
        _character(),
        [
            ProposedChange("hp_current", 40),
            ProposedChange("owner_id", 2),
            ProposedChange("sheet_data.conditions.prone", 1),
        ],
    )

    assert [change.path for change in resolved] == ["hp_current", "sheet_data.conditions.prone"]
    assert len(rejected) == 1


def test_payload_carries_columns_and_a_merged_sheet() -> None:
    character = _character(sheet_data={"conditions": {"prone": 1}, "hero_points": 2})
    resolved, _ = resolve_changes(
        character,
        [
            ProposedChange("hp_current", 40),
            ProposedChange("sheet_data.conditions.frightened", 2),
        ],
    )

    payload = build_update_payload(character, resolved)

    assert payload["hp_current"] == 40
    assert payload["sheet_data"]["conditions"] == {"prone": 1, "frightened": 2}
    # Untouched parts of the sheet must survive the patch.
    assert payload["sheet_data"]["hero_points"] == 2


def test_building_a_payload_does_not_mutate_the_stored_sheet() -> None:
    character = _character(sheet_data={"conditions": {"prone": 1}})
    resolved, _ = resolve_changes(
        character, [ProposedChange("sheet_data.conditions.frightened", 2)]
    )

    build_update_payload(character, resolved)

    assert character.sheet_data == {"conditions": {"prone": 1}}


def test_payload_creates_missing_nesting() -> None:
    character = _character(sheet_data={})
    resolved, _ = resolve_changes(
        character, [ProposedChange("sheet_data.stats.athletics.rank", "trained")]
    )

    payload = build_update_payload(character, resolved)

    assert payload["sheet_data"]["stats"]["athletics"]["rank"] == "trained"


def test_accepts_a_typed_column_that_the_model_prefixed_with_sheet_data() -> None:
    """Observed live: a small model answered "heal 20" with sheet_data.hp_max."""
    character = _character(hp_current=60, hp_max=73)

    resolved, rejected = resolve_changes(
        character,
        [
            ProposedChange(path="sheet_data.hp_current", value=80),
            ProposedChange(path="sheet_data.hp_max", value=93),
        ],
    )

    assert rejected == []
    assert [(change.path, change.value) for change in resolved] == [
        ("hp_current", 80),
        ("hp_max", 93),
    ]


def test_prefix_shortcut_does_not_open_paths_that_are_not_columns() -> None:
    _, rejected = resolve_changes(
        _character(), [ProposedChange(path="sheet_data.owner_id", value=2)]
    )

    assert len(rejected) == 1


def test_normalize_path_leaves_real_sheet_paths_alone() -> None:
    assert normalize_path("sheet_data.conditions.prone") == "sheet_data.conditions.prone"
    assert normalize_path("hp_current") == "hp_current"


def _hurt(**overrides) -> Character:
    """A character on a round 40 hit points, so the arithmetic below reads."""
    return _character(hp_max=40, hp_current=40, **overrides)


def test_a_change_without_workings_is_applied_but_marked_unverified() -> None:
    """A weak model that omits them must not be a brick wall: the player still
    gets the suggestion, just without the arithmetic vouched for."""
    resolved, rejected = resolve_changes(_hurt(), [ProposedChange(path="hp_current", value=28)])

    assert rejected == []
    assert resolved[0].value == 28
    assert resolved[0].verified is False


def test_workings_that_add_up_mark_the_change_verified() -> None:
    resolved, rejected = resolve_changes(
        _hurt(), [ProposedChange(path="hp_current", value=28, basis=40, delta=-12)]
    )

    assert rejected == []
    assert resolved[0].verified is True


def test_a_basis_the_sheet_disagrees_with_is_refused() -> None:
    """Catches the model inventing the current state instead of reading it."""
    resolved, rejected = resolve_changes(
        _hurt(), [ProposedChange(path="hp_current", value=18, basis=30, delta=-12)]
    )

    assert resolved == []
    assert "30" in rejected[0] and "40" in rejected[0]


def test_arithmetic_that_does_not_add_up_is_refused() -> None:
    """40 - 12 is 28; a model that writes 25 passes every range check."""
    resolved, rejected = resolve_changes(
        _hurt(), [ProposedChange(path="hp_current", value=25, basis=40, delta=-12)]
    )

    assert resolved == []
    assert "28" in rejected[0]


def test_a_basis_alone_is_still_checked_against_the_sheet() -> None:
    resolved, rejected = resolve_changes(
        _hurt(), [ProposedChange(path="hp_current", value=28, basis=7)]
    )

    assert resolved == []
    assert rejected


def test_workings_are_checked_inside_the_sheet_document_too() -> None:
    character = _hurt()
    character.sheet_data = {"hero_points": 2}

    resolved, rejected = resolve_changes(
        character, [ProposedChange(path="sheet_data.hero_points", value=1, basis=2, delta=-1)]
    )

    assert rejected == []
    assert resolved[0].verified is True


def test_a_rank_change_needs_no_arithmetic() -> None:
    """Ranks are words, so there is nothing to add up and nothing to demand."""
    character = _hurt()
    character.sheet_data = {"stats": {"athletics": {"rank": "trained"}}}

    resolved, rejected = resolve_changes(
        character, [ProposedChange(path="sheet_data.stats.athletics.rank", value="expert")]
    )

    assert rejected == []
    assert resolved[0].value == "expert"


def test_one_unverifiable_change_does_not_sink_the_others() -> None:
    resolved, rejected = resolve_changes(
        _hurt(),
        [
            ProposedChange(path="hp_current", value=25, basis=40, delta=-12),
            ProposedChange(path="ac", value=18),
        ],
    )

    assert [change.path for change in resolved] == ["ac"]
    assert len(rejected) == 1


def test_the_assistant_can_name_and_describe_a_character() -> None:
    """The player's own fiction: no rule can be distorted here."""
    resolved, rejected = resolve_changes(
        _character(),
        [
            ProposedChange(path="name", value="Кассий"),
            ProposedChange(path="class_name", value="Плут"),
            ProposedChange(path="sheet_data.deity", value="Нортерия"),
            ProposedChange(path="sheet_data.bio.appearance", value="Худой, шрам через бровь"),
        ],
    )

    assert rejected == []
    assert [change.value for change in resolved] == [
        "Кассий",
        "Плут",
        "Нортерия",
        "Худой, шрам через бровь",
    ]


def test_an_unknown_field_inside_a_text_group_is_refused() -> None:
    _, rejected = resolve_changes(
        _character(), [ProposedChange(path="sheet_data.bio.favourite_colour", value="синий")]
    )

    assert rejected and "favourite_colour" in rejected[0]


def test_cards_can_be_added_to_the_sheet() -> None:
    resolved, rejected = resolve_changes(
        _character(),
        [
            ProposedChange(
                path="sheet_data.inventory.ready",
                value=[{"name": "Рапира", "price": "2 зм", "bulk": "1"}],
            )
        ],
    )

    assert rejected == []
    assert resolved[0].value[0]["name"] == "Рапира"


def test_a_card_the_assistant_wrote_says_so() -> None:
    """The catalogue is not indexed yet, so this came out of the model's
    memory and the sheet must not present it as if it came from a book."""
    resolved, _ = resolve_changes(
        _character(),
        [ProposedChange(path="sheet_data.class_feats", value=[{"name": "Ловкий удар"}])],
    )

    assert resolved[0].value[0]["source"] == ASSISTANT_SOURCE


def test_a_source_the_model_cites_is_left_alone() -> None:
    resolved, _ = resolve_changes(
        _character(),
        [
            ProposedChange(
                path="sheet_data.class_feats",
                value=[{"name": "Ловкий удар", "source": "Основная книга игрока"}],
            )
        ],
    )

    assert resolved[0].value[0]["source"] == "Основная книга игрока"


def test_a_card_without_a_name_is_refused() -> None:
    """A nameless card is a row the player cannot identify or remove."""
    _, rejected = resolve_changes(
        _character(), [ProposedChange(path="sheet_data.spells", value=[{"level": 1}])]
    )

    assert rejected


def test_nested_junk_inside_a_card_is_dropped_not_stored() -> None:
    """A card is a stat block; anything nested is the model improvising a
    shape the sheet cannot render."""
    resolved, _ = resolve_changes(
        _character(),
        [
            ProposedChange(
                path="sheet_data.spells",
                value=[{"name": "Искра", "nested": {"a": 1}, "level": 1}],
            )
        ],
    )

    card = resolved[0].value[0]
    assert "nested" not in card
    assert card["level"] == 1


def test_a_card_list_that_is_not_a_list_is_refused() -> None:
    _, rejected = resolve_changes(
        _character(), [ProposedChange(path="sheet_data.spells", value="Искра")]
    )

    assert rejected


def test_a_flood_of_cards_is_refused() -> None:
    _, rejected = resolve_changes(
        _character(),
        [
            ProposedChange(
                path="sheet_data.skill_feats",
                value=[{"name": f"Черта {i}"} for i in range(MAX_CARDS + 1)],
            )
        ],
    )

    assert rejected


def test_changes_are_grouped_by_part_of_the_sheet() -> None:
    """Forty diff lines under one button is a confirmation nobody reads."""
    resolved, _ = resolve_changes(
        _character(),
        [
            ProposedChange(path="level", value=1),
            ProposedChange(path="name", value="Кассий"),
            ProposedChange(path="sheet_data.bio.age", value="24"),
            ProposedChange(path="sheet_data.inventory.worn", value=[{"name": "Кожаный доспех"}]),
        ],
    )

    assert [change.section for change in resolved] == [
        "Основное",
        "Личность",
        "Биография",
        "Снаряжение",
    ]


def test_a_filled_sheet_survives_the_round_trip() -> None:
    """The whole point: a sheet filled in one turn must come out as a patch
    the characters endpoint can write."""
    character = _character(sheet_data={})
    resolved, rejected = resolve_changes(
        character,
        [
            ProposedChange(path="class_name", value="Плут"),
            ProposedChange(path="sheet_data.heritage", value="Полуэльф"),
            ProposedChange(path="sheet_data.bio.age", value="24"),
            ProposedChange(path="sheet_data.inventory.ready", value=[{"name": "Рапира"}]),
        ],
    )
    payload = build_update_payload(character, resolved)

    assert rejected == []
    assert payload["class_name"] == "Плут"
    assert payload["sheet_data"]["heritage"] == "Полуэльф"
    assert payload["sheet_data"]["bio"]["age"] == "24"
    assert payload["sheet_data"]["inventory"]["ready"][0]["name"] == "Рапира"


def test_a_stat_path_missing_its_stats_segment_is_understood() -> None:
    """Seen in a real answer: sheet_data.perception.rank for what lives at
    sheet_data.stats.perception.rank. The stat and the part are both named,
    so refusing it on a path technicality throws away a sound suggestion."""
    assert normalize_path("sheet_data.perception.rank") == "sheet_data.stats.perception.rank"


def test_normalisation_does_not_invent_a_stat() -> None:
    assert normalize_path("sheet_data.cooking.rank") == "sheet_data.cooking.rank"


def test_a_text_column_the_model_prefixed_with_sheet_data_is_understood() -> None:
    """Observed live: a character build wrote sheet_data.ancestry,
    sheet_data.background and sheet_data.class_name — the same shortcut
    already forgiven for hp_current, just for the text columns instead of
    the numeric ones."""
    assert normalize_path("sheet_data.ancestry") == "ancestry"
    assert normalize_path("sheet_data.background") == "background"
    assert normalize_path("sheet_data.class_name") == "class_name"


def test_a_text_column_under_the_sheet_prefix_is_understood() -> None:
    """Observed filling a sheet: the model wrote sheet_data.ancestry and
    sheet_data.class_name, and both were refused as "not editable" although
    those fields are open — the prefix was only stripped for numeric columns.
    The refusal read as a policy when it was a naming miss."""
    assert normalize_path("sheet_data.ancestry") == "ancestry"
    assert normalize_path("sheet_data.class_name") == "class_name"
    assert normalize_path("sheet_data.name") == "name"


def test_an_ability_modifier_nested_under_stats_is_understood() -> None:
    """Observed live: sheet_data.stats.dex_mod for what is the typed column
    dex_mod. The model reused the "stats." prefix it saw work for skills."""
    for ability in ("str", "dex", "con", "int", "wis", "cha"):
        assert normalize_path(f"sheet_data.stats.{ability}_mod") == f"{ability}_mod"


def test_a_skill_rank_under_the_wrong_group_name_is_understood() -> None:
    """Observed live: sheet_data.skills.acrobatics.rank for what lives at
    sheet_data.stats.acrobatics.rank — "skills" reads as the obvious folder
    name and is not the one the sheet actually uses."""
    assert normalize_path("sheet_data.skills.acrobatics.rank") == "sheet_data.stats.acrobatics.rank"


def test_a_save_rank_under_the_wrong_group_name_is_understood() -> None:
    """Observed live: sheet_data.saving_throws.fortitude.rank for what lives
    at sheet_data.stats.fortitude.rank."""
    assert (
        normalize_path("sheet_data.saving_throws.fortitude.rank")
        == "sheet_data.stats.fortitude.rank"
    )


def test_a_skill_written_under_a_skills_container_is_understood() -> None:
    """Also observed: sheet_data.skills.Acrobatics.rank. Ranks are editable,
    but they live under stats, and the model capitalised the name."""
    assert normalize_path("sheet_data.skills.Acrobatics.rank") == "sheet_data.stats.acrobatics.rank"
    assert normalize_path("sheet_data.skills.stealth.rank") == "sheet_data.stats.stealth.rank"


def test_the_skills_container_does_not_invent_a_skill() -> None:
    assert normalize_path("sheet_data.skills.Juggling.rank") == "sheet_data.skills.Juggling.rank"


def test_a_group_alias_does_not_invent_a_stat() -> None:
    """The alias only forgives the folder name — an unknown stat must still
    fall through to resolve_change and be refused there, not be silently
    accepted."""
    assert normalize_path("sheet_data.skills.cooking.rank") == "sheet_data.skills.cooking.rank"


def test_a_group_alias_still_lets_an_unknown_part_be_refused_specifically() -> None:
    """The part after a real stat is not checked by the alias itself: it is
    rewritten to sheet_data.stats.<stat>.modifier and refused there, with a
    message about "modifier" rather than a generic path-not-found."""
    assert (
        normalize_path("sheet_data.skills.acrobatics.modifier")
        == "sheet_data.stats.acrobatics.modifier"
    )


def test_a_modifier_written_directly_is_refused_not_silently_dropped() -> None:
    """The displayed modifier is computed from rank, item and temporary — not
    a field of its own. A model that tries to set it directly (observed live,
    for both skills and saves) must be told why, not just "path unavailable"."""
    with pytest.raises(ChangeRejected, match="нельзя менять"):
        resolve_change(
            _character(),
            ProposedChange(path="sheet_data.skills.acrobatics.modifier", value=6),
        )
    with pytest.raises(ChangeRejected, match="нельзя менять"):
        resolve_change(
            _character(),
            ProposedChange(path="sheet_data.saving_throws.fortitude.modifier", value=6),
        )


def test_the_rogue_build_from_the_field_report_goes_through() -> None:
    """A compact version of the exact proposal that triggered this fix: every
    path here was rejected before normalize_path learned these three shapes."""
    resolved, rejected = resolve_changes(
        _character(level=1, sheet_data={}),
        [
            ProposedChange(path="sheet_data.ancestry", value="Человек"),
            ProposedChange(path="sheet_data.background", value="Pathfinder Recruiter"),
            ProposedChange(path="sheet_data.class_name", value="Плут"),
            ProposedChange(path="sheet_data.stats.dex_mod", value=4),
            ProposedChange(path="sheet_data.skills.acrobatics.rank", value="trained"),
            ProposedChange(path="sheet_data.saving_throws.reflex.rank", value="trained"),
        ],
    )

    assert rejected == []
    assert {change.path for change in resolved} == {
        "ancestry",
        "background",
        "class_name",
        "dex_mod",
        "sheet_data.stats.acrobatics.rank",
        "sheet_data.stats.reflex.rank",
    }


def test_a_list_of_languages_is_accepted_as_a_list_of_words() -> None:
    """The sheet stores languages as one line, and the model offered
    ["Common", "Elven"] — a reasonable shape for a plainly plural field.
    Refusing it made the assistant look unable to fill a field it had in
    fact filled correctly."""
    character = _character()

    resolved, rejected = resolve_changes(
        character,
        [ProposedChange(path="sheet_data.languages", value=["Common", "Elven"])],
    )

    assert rejected == []
    assert resolved[0].value == "Common, Elven"


def test_a_list_of_objects_is_still_not_a_line_of_text() -> None:
    """Joining anything at all would turn a wrong shape into plausible junk."""
    character = _character()

    _, rejected = resolve_changes(
        character,
        [ProposedChange(path="sheet_data.languages", value=[{"name": "Common"}])],
    )

    assert rejected


def test_a_computed_modifier_is_still_refused() -> None:
    """A modifier is derived from rank, ability and level. Accepting one
    directly would let the sheet disagree with its own arithmetic, so this
    stays refused even once the path is understood — normalize_path now
    resolves the container and the capitalised skill (that part is no
    longer in doubt), and resolve_change refuses the field it names."""
    assert (
        normalize_path("sheet_data.skills.Acrobatics.modifier")
        == "sheet_data.stats.acrobatics.modifier"
    )
    with pytest.raises(ChangeRejected, match="нельзя менять"):
        resolve_change(
            _character(),
            ProposedChange(path="sheet_data.skills.Acrobatics.modifier", value=6),
        )
