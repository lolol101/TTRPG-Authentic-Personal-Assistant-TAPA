"""Asking the rulebooks in the language they are written in — once per concept.

The corpus is English. Measured on this index, the page answering an
English question sits at ranks 1-13; the page answering the same question
in Russian sits at 20-50 or lower. So the question is named in the book's
own terms and searched a second time — and when that fails, the request
must be left exactly as it was.

A question can also name more than one rule at once ("можно ли схватить,
если я напуган"), and naming it as a single query drops one of them: see
the measurement quoted in app/core/query_rewrite.py. So the rewrite yields
a list, and every concept in it gets its own search.
"""

import json

import pytest

from app.core import query_rewrite
from app.core.config import settings
from app.core.llm_provider import Completion
from app.core.tools import REWRITE_SEARCH_QUERY


def _rewritten(*queries: str) -> Completion:
    return Completion(
        text="",
        provider="test",
        tool_arguments={REWRITE_SEARCH_QUERY: json.dumps({"queries": list(queries)})},
    )


def test_a_russian_question_is_named_in_the_books_own_terms(monkeypatch) -> None:
    monkeypatch.setattr(
        query_rewrite, "_ask_for_rewrite", lambda question: _rewritten("Demoralize action")
    )

    assert query_rewrite.search_queries_for("Что делает действие Устрашение?") == [
        "Demoralize action"
    ]


def test_a_question_naming_two_rules_is_searched_for_both(monkeypatch) -> None:
    """The measured failure this exists for: asked as one query, the rewrite
    keeps whichever concept came first and the other is never searched."""
    monkeypatch.setattr(
        query_rewrite,
        "_ask_for_rewrite",
        lambda question: _rewritten("Grapple action", "Frightened condition"),
    )

    assert query_rewrite.search_queries_for("Могу ли я схватить противника, если сам напуган?") == [
        "Grapple action",
        "Frightened condition",
    ]


def test_a_question_the_model_leaves_alone_is_searched_as_asked(monkeypatch) -> None:
    """No tool call is the model saying the question is already searchable;
    that must cost the request nothing but the one call."""
    monkeypatch.setattr(
        query_rewrite, "_ask_for_rewrite", lambda question: Completion(text="", provider="test")
    )

    assert query_rewrite.search_queries_for("Demoralize action") == []


def test_a_rewrite_identical_to_the_question_is_dropped(monkeypatch) -> None:
    """Searching the same string twice costs an embedding and returns the
    same hits."""
    monkeypatch.setattr(
        query_rewrite, "_ask_for_rewrite", lambda question: _rewritten("Grapple ACTION")
    )

    assert query_rewrite.search_queries_for("grapple action") == []


def test_the_same_concept_named_twice_is_searched_once(monkeypatch) -> None:
    monkeypatch.setattr(
        query_rewrite,
        "_ask_for_rewrite",
        lambda question: _rewritten("Grapple action", "grapple ACTION"),
    )

    assert query_rewrite.search_queries_for("Как работает захват?") == ["Grapple action"]


def test_the_number_of_searches_is_capped(monkeypatch) -> None:
    """Each query is an embedding and a search, and they all land in one
    prompt — past a few, the context the retrieval protects is the thing
    being spent."""
    monkeypatch.setattr(settings, "retrieval_max_search_queries", 3)
    monkeypatch.setattr(
        query_rewrite,
        "_ask_for_rewrite",
        lambda question: _rewritten("one", "two", "three", "four", "five"),
    )

    assert query_rewrite.search_queries_for("Длинный составной вопрос") == ["one", "two", "three"]


def test_a_single_query_is_still_accepted(monkeypatch) -> None:
    """Models answer a list-valued argument with a bare string often enough
    that refusing it would silently cost the request its rewrite."""
    monkeypatch.setattr(
        query_rewrite,
        "_ask_for_rewrite",
        lambda question: Completion(
            text="",
            provider="test",
            tool_arguments={REWRITE_SEARCH_QUERY: json.dumps({"query": "Demoralize action"})},
        ),
    )

    assert query_rewrite.search_queries_for("Что делает действие Устрашение?") == [
        "Demoralize action"
    ]


@pytest.mark.parametrize(
    "broken",
    [
        "not json",
        "[]",
        '{"queries": []}',
        '{"queries": ""}',
        '{"queries": [""]}',
        '{"queries": ["   "]}',
        '{"query": ""}',
        '{"query": "   "}',
        "",
    ],
)
def test_an_unusable_rewrite_degrades_to_the_plain_search(monkeypatch, broken) -> None:
    monkeypatch.setattr(
        query_rewrite,
        "_ask_for_rewrite",
        lambda question: Completion(
            text="", provider="test", tool_arguments={REWRITE_SEARCH_QUERY: broken}
        ),
    )

    assert query_rewrite.search_queries_for("Что делает действие Захват?") == []


def test_an_answer_instead_of_a_query_is_refused(monkeypatch) -> None:
    """A paragraph back means the model answered the question rather than
    naming it — embedding its prose retrieves its own guesses, not the rule."""
    monkeypatch.setattr(
        query_rewrite,
        "_ask_for_rewrite",
        lambda question: _rewritten("Устрашение — это " + "x" * 300),
    )

    assert query_rewrite.search_queries_for("Что делает действие Устрашение?") == []


def test_one_unusable_query_does_not_discard_the_others(monkeypatch) -> None:
    monkeypatch.setattr(
        query_rewrite,
        "_ask_for_rewrite",
        lambda question: _rewritten("x" * 300, "Frightened condition"),
    )

    assert query_rewrite.search_queries_for("Составной вопрос") == ["Frightened condition"]


def test_a_provider_failure_degrades_to_the_plain_search(monkeypatch) -> None:
    def _boom(question):
        raise RuntimeError("provider down")

    monkeypatch.setattr(query_rewrite, "_ask_for_rewrite", _boom)

    assert query_rewrite.search_queries_for("Что делает действие Захват?") == []
