from pathlib import Path

import pytest

from app.models import RawPage
from app.parser import UnrecognizedPageError, category_from_url, parse_page

FIXTURE = Path(__file__).parent / "fixtures" / "action_strike.html"


def _load_fixture() -> RawPage:
    html = FIXTURE.read_text(encoding="utf-8")
    return RawPage(
        url="https://pf2.ru/actions/strike",
        html=html,
        fetched_at="2026-01-01T00:00:00+00:00",
    )


def test_parses_title_without_noise() -> None:
    parsed = parse_page(_load_fixture())

    assert parsed.title == "Удар"


def test_parses_traits() -> None:
    parsed = parse_page(_load_fixture())

    assert parsed.traits == ["Атака"]


def test_parses_source_book() -> None:
    parsed = parse_page(_load_fixture())

    assert parsed.source_book == "Основная книга игрока"


def test_body_contains_russian_rule_text_only() -> None:
    parsed = parse_page(_load_fixture())

    assert "Вы атакуете используемым оружием" in parsed.body
    assert "Критический успех" in parsed.body
    assert "ПАРАМЕТРЫ УДАРОВ" in parsed.body
    # The source line and the hidden English duplicate must not leak in.
    assert "Источник" not in parsed.body
    assert "You attack with a weapon" not in parsed.body


def test_category_from_url() -> None:
    assert category_from_url("https://pf2.ru/actions/strike") == "actions"
    assert category_from_url("https://pf2.ru/ancestries/dwarf") == "ancestries"


def test_unrecognized_page_raises() -> None:
    page = RawPage(
        url="https://pf2.ru/ancestries/dwarf",
        html="<html><body><div id='main-content'>no item-content-ru here</div></body></html>",
        fetched_at="2026-01-01T00:00:00+00:00",
    )

    with pytest.raises(UnrecognizedPageError):
        parse_page(page)
