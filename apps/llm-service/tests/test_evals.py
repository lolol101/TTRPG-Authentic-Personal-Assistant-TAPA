"""Covers the eval checker itself — the golden run needs a live service."""

import json
from pathlib import Path

from evals.run_evals import GOLDEN_PATH, check_case


def test_golden_set_is_valid_and_every_case_asserts_something() -> None:
    golden = json.loads(Path(GOLDEN_PATH).read_text(encoding="utf-8"))

    assert golden["cases"], "golden-набор пуст"
    for case in golden["cases"]:
        assert case["name"]
        assert case["question"]
        assert case["expect"], f"{case['name']}: нет ожиданий — случай ничего не проверяет"


def test_any_of_passes_when_one_substring_matches() -> None:
    case = {"expect": {"any_of": ["захват", "борьба"]}}

    assert check_case(case, "Это действие про Захват цели.", []) == []


def test_any_of_fails_when_nothing_matches() -> None:
    case = {"expect": {"any_of": ["захват"]}}

    assert check_case(case, "Совершенно другой ответ.", [])


def test_none_of_fails_when_a_forbidden_substring_appears() -> None:
    case = {"expect": {"none_of": ["+12"]}}

    assert check_case(case, "Твой модификатор +12.", [])


def test_sources_non_empty_fails_on_an_ungrounded_answer() -> None:
    case = {"expect": {"sources_non_empty": True}}

    assert check_case(case, "Какой-то ответ", [])
    assert check_case(case, "Какой-то ответ", [{"title": "Захват"}]) == []


def test_matching_ignores_case() -> None:
    case = {"expect": {"any_of": ["ЗАХВАТ"]}}

    assert check_case(case, "речь про захват", []) == []
