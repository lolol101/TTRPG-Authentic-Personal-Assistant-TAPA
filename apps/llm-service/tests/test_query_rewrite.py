"""Preparing a question for search: on its own, and in the books' language.

The corpus is English. Measured on this index, the page answering an
English question sits at ranks 1-13; the page answering the same question
in Russian sits at 20-50 or lower. So the question is named in the book's
own terms, once per rule it names (see app/core/query_rewrite.py for the
measurement behind the list).

The same call restates the question so it reads without the dialogue: a
follow-up gets its subject filled in, a new topic must not drag the old one
in. When the call fails, the request must be left exactly as it was.
"""

import json

import pytest

from app.core import query_rewrite
from app.core.config import settings
from app.core.history import Turn
from app.core.llm_provider import Completion
from app.core.tools import REWRITE_SEARCH_QUERY


def _rewritten(*queries: str, standalone: str | None = "вопрос") -> Completion:
    arguments: dict = {"queries": list(queries)}
    if standalone is not None:
        arguments["standalone_question"] = standalone
    return Completion(
        text="", provider="test", tool_arguments={REWRITE_SEARCH_QUERY: json.dumps(arguments)}
    )


def _answers(monkeypatch, completion: Completion) -> list[tuple[str, list[Turn]]]:
    calls: list[tuple[str, list[Turn]]] = []

    def _fake(question, history):
        calls.append((question, history))
        return completion

    monkeypatch.setattr(query_rewrite, "_ask_for_rewrite", _fake)
    return calls


def test_a_russian_question_is_named_in_the_books_own_terms(monkeypatch) -> None:
    _answers(monkeypatch, _rewritten("Demoralize action", standalone="Что делает Устрашение?"))

    rewrite = query_rewrite.rewrite_question("Что делает действие Устрашение?", [])

    assert rewrite.queries == ["Demoralize action"]


def test_a_follow_up_comes_back_with_its_subject_filled_in(monkeypatch) -> None:
    history = [
        Turn(role="user", text="Что делает действие Захват?"),
        Turn(role="assistant", text="Захват требует свободной руки..."),
    ]
    calls = _answers(
        monkeypatch,
        _rewritten("Grapple heavy armor", standalone="Можно ли схватить цель в тяжёлой броне?"),
    )

    rewrite = query_rewrite.rewrite_question("А если он в тяжёлой броне?", history)

    assert rewrite.standalone == "Можно ли схватить цель в тяжёлой броне?"
    assert calls[0][1] == history


def test_the_rewrite_sees_only_the_recent_dialogue_with_answers_cut_short(monkeypatch) -> None:
    """Enough to resolve "он" or "второй вариант"; the rest only slows the
    call and drags older topics into it."""
    monkeypatch.setattr(settings, "rewrite_history_messages", 2)
    monkeypatch.setattr(settings, "rewrite_history_answer_chars", 10)
    history = [
        Turn(role="user", text="Старый вопрос про сеттинг"),
        Turn(role="assistant", text="старый ответ"),
        Turn(role="user", text="Что делает Захват?"),
        Turn(role="assistant", text="Захват требует свободной руки и проверки Атлетики"),
    ]

    dialogue = query_rewrite._dialogue(history)

    assert "Старый вопрос" not in dialogue
    assert "Игрок: Что делает Захват?" in dialogue
    assert "Ассистент: Захват тре" in dialogue
    assert "Атлетики" not in dialogue


def test_a_question_naming_two_rules_is_searched_for_both(monkeypatch) -> None:
    """The measured failure this exists for: asked as one query, the rewrite
    keeps whichever concept came first and the other is never searched."""
    _answers(monkeypatch, _rewritten("Grapple action", "Frightened condition"))

    rewrite = query_rewrite.rewrite_question("Могу ли я схватить противника, если напуган?", [])

    assert rewrite.queries == ["Grapple action", "Frightened condition"]


def test_a_query_identical_to_the_question_or_its_restatement_is_dropped(monkeypatch) -> None:
    """Searching the same string twice costs an embedding and returns the
    same hits."""
    _answers(monkeypatch, _rewritten("Grapple ACTION", "Grapple rules", standalone="grapple rules"))

    rewrite = query_rewrite.rewrite_question("grapple action", [])

    assert rewrite.queries == []


def test_the_same_concept_named_twice_is_searched_once(monkeypatch) -> None:
    _answers(monkeypatch, _rewritten("Grapple action", "grapple ACTION"))

    assert query_rewrite.rewrite_question("Как работает захват?", []).queries == ["Grapple action"]


def test_the_number_of_searches_is_capped(monkeypatch) -> None:
    """Each query is an embedding and a search, and they all land in one
    prompt — past a few, the context the retrieval protects is the thing
    being spent."""
    monkeypatch.setattr(settings, "retrieval_max_search_queries", 3)
    _answers(monkeypatch, _rewritten("one", "two", "three", "four", "five"))

    assert query_rewrite.rewrite_question("Длинный составной вопрос", []).queries == [
        "one",
        "two",
        "three",
    ]


def test_a_single_query_is_still_accepted(monkeypatch) -> None:
    """Models answer a list-valued argument with a bare string often enough
    that refusing it would silently cost the request its rewrite."""
    _answers(
        monkeypatch,
        Completion(
            text="",
            provider="test",
            tool_arguments={REWRITE_SEARCH_QUERY: json.dumps({"query": "Demoralize action"})},
        ),
    )

    assert query_rewrite.rewrite_question("Что делает Устрашение?", []).queries == [
        "Demoralize action"
    ]


def test_queries_without_a_restatement_still_search(monkeypatch) -> None:
    """No usable restatement means the caller keeps the old glued search;
    the English queries are still worth running in front of it."""
    _answers(monkeypatch, _rewritten("Demoralize action", standalone=None))

    rewrite = query_rewrite.rewrite_question("Что делает Устрашение?", [])

    assert rewrite.standalone is None
    assert rewrite.queries == ["Demoralize action"]


def test_an_answer_instead_of_a_restatement_is_refused(monkeypatch) -> None:
    _answers(monkeypatch, _rewritten("Demoralize action", standalone="Устрашение — " + "x" * 600))

    assert query_rewrite.rewrite_question("Что делает Устрашение?", []).standalone is None


@pytest.mark.parametrize(
    "broken",
    ["not json", "[]", '{"queries": []}', '{"queries": [""]}', '{"query": "   "}', ""],
)
def test_an_unusable_rewrite_degrades_to_the_plain_search(monkeypatch, broken) -> None:
    _answers(
        monkeypatch,
        Completion(text="", provider="test", tool_arguments={REWRITE_SEARCH_QUERY: broken}),
    )

    rewrite = query_rewrite.rewrite_question("Что делает действие Захват?", [])

    assert rewrite.queries == []
    assert rewrite.standalone is None


def test_no_tool_call_degrades_to_the_plain_search(monkeypatch) -> None:
    _answers(monkeypatch, Completion(text="Захват — это...", provider="test"))

    assert query_rewrite.rewrite_question("Что делает Захват?", []) == query_rewrite.Rewrite()


def test_an_answer_instead_of_a_query_is_refused(monkeypatch) -> None:
    """A paragraph back means the model answered the question rather than
    naming it — embedding its prose retrieves its own guesses, not the rule."""
    _answers(monkeypatch, _rewritten("Устрашение — это " + "x" * 300))

    assert query_rewrite.rewrite_question("Что делает Устрашение?", []).queries == []


def test_a_provider_failure_degrades_to_the_plain_search(monkeypatch) -> None:
    def _boom(question, history):
        raise RuntimeError("provider down")

    monkeypatch.setattr(query_rewrite, "_ask_for_rewrite", _boom)

    assert query_rewrite.rewrite_question("Что делает Захват?", []) == query_rewrite.Rewrite()
