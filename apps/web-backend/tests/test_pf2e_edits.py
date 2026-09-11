import pytest

from app.models.character import Character
from app.rulesets.pf2e.edits import (
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
    with pytest.raises(ChangeRejected, match="недоступен для правки"):
        resolve_change(_character(), ProposedChange("name", "Другое имя"))


def test_refuses_arbitrary_sheet_paths() -> None:
    with pytest.raises(ChangeRejected, match="недоступен для правки"):
        resolve_change(_character(), ProposedChange("sheet_data.player_name", "Никита"))


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


def test_rejects_a_non_numeric_value_for_a_number_field() -> None:
    with pytest.raises(ChangeRejected, match="ожидалось число"):
        resolve_change(_character(), ProposedChange("hp_current", "много"))


def test_one_bad_proposal_does_not_discard_the_good_ones() -> None:
    resolved, rejected = resolve_changes(
        _character(),
        [
            ProposedChange("hp_current", 40),
            ProposedChange("name", "взлом"),
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
