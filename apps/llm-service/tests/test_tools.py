from app.core.tools import SHEET_CHANGE_TOOL, parse_change_arguments


def test_reads_the_documented_shape() -> None:
    raw = '{"changes": [{"path": "hp_current", "value": 42, "reason": "урон"}]}'

    assert parse_change_arguments(raw) == [
        {"path": "hp_current", "value": 42, "reason": "урон", "basis": None, "delta": None}
    ]


def test_accepts_a_bare_list_of_changes() -> None:
    raw = '[{"path": "hp_current", "value": 5}]'

    assert parse_change_arguments(raw) == [
        {"path": "hp_current", "value": 5, "reason": "", "basis": None, "delta": None}
    ]


def test_accepts_a_single_change_object() -> None:
    """Some models answer with one change instead of a list of one."""
    raw = '{"changes": {"path": "sheet_data.hero_points", "value": 2}}'

    assert parse_change_arguments(raw) == [
        {"path": "sheet_data.hero_points", "value": 2, "reason": "", "basis": None, "delta": None}
    ]


def test_malformed_json_yields_no_proposals_rather_than_failing() -> None:
    # The text answer is still useful; a broken tool call must not lose it.
    assert parse_change_arguments("не json") == []


def test_entries_without_a_path_are_dropped() -> None:
    raw = '{"changes": [{"value": 1}, {"path": "hp_current", "value": 2}]}'

    assert parse_change_arguments(raw) == [
        {"path": "hp_current", "value": 2, "reason": "", "basis": None, "delta": None}
    ]


def test_missing_changes_key_yields_nothing() -> None:
    assert parse_change_arguments('{"foo": "bar"}') == []


def test_the_workings_are_carried_through_when_given() -> None:
    """web-backend checks basis and delta against the sheet; dropping them
    here would quietly turn every verified change into an unverified one."""
    raw = '{"changes": [{"path": "hp_current", "value": 28, "basis": 40, "delta": -12}]}'

    assert parse_change_arguments(raw) == [
        {"path": "hp_current", "value": 28, "reason": "", "basis": 40, "delta": -12}
    ]


def test_the_card_field_lists_name_what_a_stat_block_holds() -> None:
    """A card arriving with only a name was partly this: the schema named
    level, price, bulk and description as examples and left the model to
    guess the rest existed."""
    described = SHEET_CHANGE_TOOL["function"]["parameters"]["properties"]["changes"]["items"][
        "properties"
    ]["value"]["description"]

    for field in ("prerequisites", "requirements", "frequency", "actions", "traits", "special"):
        assert field in described


def test_the_card_schema_tells_the_model_not_to_invent_a_missing_field() -> None:
    described = SHEET_CHANGE_TOOL["function"]["parameters"]["properties"]["changes"]["items"][
        "properties"
    ]["value"]["description"]

    assert "оставляй пустым" in described
