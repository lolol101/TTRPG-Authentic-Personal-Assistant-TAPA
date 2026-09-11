from app.core.tools import parse_change_arguments


def test_reads_the_documented_shape() -> None:
    raw = '{"changes": [{"path": "hp_current", "value": 42, "reason": "урон"}]}'

    assert parse_change_arguments(raw) == [
        {"path": "hp_current", "value": 42, "reason": "урон"}
    ]


def test_accepts_a_bare_list_of_changes() -> None:
    raw = '[{"path": "hp_current", "value": 5}]'

    assert parse_change_arguments(raw) == [{"path": "hp_current", "value": 5, "reason": ""}]


def test_accepts_a_single_change_object() -> None:
    """Some models answer with one change instead of a list of one."""
    raw = '{"changes": {"path": "sheet_data.hero_points", "value": 2}}'

    assert parse_change_arguments(raw) == [
        {"path": "sheet_data.hero_points", "value": 2, "reason": ""}
    ]


def test_malformed_json_yields_no_proposals_rather_than_failing() -> None:
    # The text answer is still useful; a broken tool call must not lose it.
    assert parse_change_arguments("не json") == []


def test_entries_without_a_path_are_dropped() -> None:
    raw = '{"changes": [{"value": 1}, {"path": "hp_current", "value": 2}]}'

    assert parse_change_arguments(raw) == [{"path": "hp_current", "value": 2, "reason": ""}]


def test_missing_changes_key_yields_nothing() -> None:
    assert parse_change_arguments('{"foo": "bar"}') == []
