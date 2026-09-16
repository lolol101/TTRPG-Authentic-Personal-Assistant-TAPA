"""Asking the rulebooks in the language they are written in.

The corpus is English. Measured on this index, the page answering an
English question sits at ranks 1-13; the page answering the same question
in Russian sits at 20-50 or lower. So the question is named in the book's
own terms and searched a second time — and when that fails, the request
must be left exactly as it was.
"""

import json

import pytest

from app.core import query_rewrite
from app.core.llm_provider import Completion
from app.core.tools import REWRITE_SEARCH_QUERY


def _rewritten(query: str) -> Completion:
    return Completion(
        text="",
        provider="test",
        tool_arguments={REWRITE_SEARCH_QUERY: json.dumps({"query": query})},
    )


def test_a_russian_question_is_named_in_the_books_own_terms(monkeypatch) -> None:
    monkeypatch.setattr(
        query_rewrite, "_ask_for_rewrite", lambda question: _rewritten("Demoralize action")
    )

    assert query_rewrite.rewrite_for_search("Что делает действие Устрашение?") == (
        "Demoralize action"
    )


def test_a_question_the_model_leaves_alone_is_searched_as_asked(monkeypatch) -> None:
    """No tool call is the model saying the question is already searchable;
    that must cost the request nothing but the one call."""
    monkeypatch.setattr(
        query_rewrite, "_ask_for_rewrite", lambda question: Completion(text="", provider="test")
    )

    assert query_rewrite.rewrite_for_search("Demoralize action") is None


def test_a_rewrite_identical_to_the_question_is_dropped(monkeypatch) -> None:
    """Searching the same string twice costs an embedding and returns the
    same hits."""
    monkeypatch.setattr(
        query_rewrite, "_ask_for_rewrite", lambda question: _rewritten("Grapple ACTION")
    )

    assert query_rewrite.rewrite_for_search("grapple action") is None


@pytest.mark.parametrize("broken", ["not json", "[]", '{"query": ""}', '{"query": "   "}', ""])
def test_an_unusable_rewrite_degrades_to_the_plain_search(monkeypatch, broken) -> None:
    monkeypatch.setattr(
        query_rewrite,
        "_ask_for_rewrite",
        lambda question: Completion(
            text="", provider="test", tool_arguments={REWRITE_SEARCH_QUERY: broken}
        ),
    )

    assert query_rewrite.rewrite_for_search("Что делает действие Захват?") is None


def test_an_answer_instead_of_a_query_is_refused(monkeypatch) -> None:
    """A paragraph back means the model answered the question rather than
    naming it — embedding its prose retrieves its own guesses, not the rule."""
    monkeypatch.setattr(
        query_rewrite,
        "_ask_for_rewrite",
        lambda question: _rewritten("Устрашение — это " + "x" * 300),
    )

    assert query_rewrite.rewrite_for_search("Что делает действие Устрашение?") is None


def test_a_provider_failure_degrades_to_the_plain_search(monkeypatch) -> None:
    def _boom(question):
        raise RuntimeError("provider down")

    monkeypatch.setattr(query_rewrite, "_ask_for_rewrite", _boom)

    assert query_rewrite.rewrite_for_search("Что делает действие Захват?") is None
