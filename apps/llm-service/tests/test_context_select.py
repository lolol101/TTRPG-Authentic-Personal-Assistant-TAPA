"""Narrowing retrieved rules to what answers the question.

What this protects: the distance cut drops only what is past the limit; the
model's judgement can shrink the context to nothing, which must read as
"the books say nothing"; and a judgement that cannot be read, or a provider
that fails, must leave the request on everything it retrieved — never on
less than it would have had without this step.
"""

import json

import pytest

from app.core import context_select
from app.core.config import settings
from app.core.llm_provider import Completion
from app.core.tools import PICK_FRAGMENTS, WRITE_EXTRACT


def _hit(title: str, distance: float = 0.6) -> dict:
    return {
        "id": title,
        "text": f"{title} rules text",
        "metadata": {"title": title, "url": f"https://example.invalid/{title}", "source_book": ""},
        "distance": distance,
    }


HITS = [_hit("Grapple"), _hit("Shove"), _hit("Frightened")]


def _titles(chunks: list[dict]) -> list[str]:
    return [chunk["metadata"]["title"] for chunk in chunks]


def _answers(monkeypatch, tool: str, arguments) -> None:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    monkeypatch.setattr(
        context_select,
        "_ask",
        lambda question, retrieved: Completion(
            text="", provider="test", tool_arguments={tool: raw}
        ),
    )


def _must_not_call(question, retrieved):
    raise AssertionError("no model call expected here")


def test_hits_past_the_distance_limit_are_dropped(monkeypatch) -> None:
    monkeypatch.setattr(settings, "retrieval_max_distance", 0.9)
    hits = [_hit("near", 0.62), _hit("edge", 0.9), _hit("garbage", 0.95)]

    assert _titles(context_select.within_distance(hits)) == ["near", "edge"]


def test_off_makes_no_call(monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_mode", "off")
    monkeypatch.setattr(context_select, "_ask", _must_not_call)

    assert context_select.narrow("вопрос", HITS).chunks == HITS


@pytest.mark.parametrize("mode", ["select", "digest"])
def test_nothing_retrieved_costs_no_call(monkeypatch, mode) -> None:
    """The point of the distance cut: an off-topic question arrives here
    empty and must not pay for a judgement of nothing."""
    monkeypatch.setattr(settings, "context_mode", mode)
    monkeypatch.setattr(context_select, "_ask", _must_not_call)

    assert context_select.narrow("столица Франции", []).chunks == []


def test_select_keeps_only_the_named_fragments_in_retrieval_order(monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_mode", "select")
    _answers(monkeypatch, PICK_FRAGMENTS, {"numbers": [3, 1]})

    context = context_select.narrow("Могу ли я схватить, если напуган?", HITS)

    assert _titles(context.chunks) == ["Grapple", "Frightened"]
    assert context.digest is None


def test_select_with_nothing_relevant_leaves_no_context(monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_mode", "select")
    _answers(monkeypatch, PICK_FRAGMENTS, {"numbers": []})

    assert context_select.narrow("Что такое THAC0?", HITS).chunks == []


def test_select_ignores_numbers_that_name_no_fragment(monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_mode", "select")
    _answers(monkeypatch, PICK_FRAGMENTS, {"numbers": [0, 2, "2", 9, "x"]})

    assert _titles(context_select.narrow("вопрос", HITS).chunks) == ["Shove"]


@pytest.mark.parametrize("broken", ["not json", "[]", '{"numbers": "1"}', "{}"])
def test_an_unreadable_selection_keeps_everything(monkeypatch, broken) -> None:
    monkeypatch.setattr(settings, "context_mode", "select")
    _answers(monkeypatch, PICK_FRAGMENTS, broken)

    assert context_select.narrow("вопрос", HITS).chunks == HITS


@pytest.mark.parametrize("mode", ["select", "digest"])
def test_no_tool_call_keeps_everything(monkeypatch, mode) -> None:
    """Told to always call the tool, so silence is not "nothing relevant" —
    reading it that way would turn a model's lapse into a refusal."""
    monkeypatch.setattr(settings, "context_mode", mode)
    monkeypatch.setattr(
        context_select,
        "_ask",
        lambda question, retrieved: Completion(text="Захват — это...", provider="test"),
    )

    assert context_select.narrow("вопрос", HITS).chunks == HITS


@pytest.mark.parametrize("mode", ["select", "digest"])
def test_a_provider_failure_keeps_everything(monkeypatch, mode) -> None:
    monkeypatch.setattr(settings, "context_mode", mode)

    def _boom(question, retrieved):
        raise RuntimeError("provider down")

    monkeypatch.setattr(context_select, "_ask", _boom)

    assert context_select.narrow("вопрос", HITS).chunks == HITS


def test_digest_cites_only_the_fragments_it_used_renumbered(monkeypatch) -> None:
    """The answer sees the used pages alone, numbered from 1, so the
    extract's citations have to follow or they point at the wrong page."""
    monkeypatch.setattr(settings, "context_mode", "digest")
    _answers(
        monkeypatch,
        WRITE_EXTRACT,
        {
            "extract": "Grapple needs a free hand [1]. Frightened: status penalty [3].",
            "used": [1, 3],
        },
    )

    context = context_select.narrow("Могу ли я схватить, если напуган?", HITS)

    assert _titles(context.chunks) == ["Grapple", "Frightened"]
    assert context.digest == "Grapple needs a free hand [1]. Frightened: status penalty [2]."


def test_digest_with_nothing_relevant_leaves_no_context(monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_mode", "digest")
    _answers(monkeypatch, WRITE_EXTRACT, {"extract": "", "used": []})

    context = context_select.narrow("Что такое THAC0?", HITS)

    assert context.chunks == []


@pytest.mark.parametrize(
    "broken",
    [
        {"extract": "Grapple needs a free hand.", "used": []},
        {"extract": "", "used": [1]},
        {"extract": 5, "used": [1]},
        {"extract": "text [1]"},
        "not json",
    ],
)
def test_an_unreadable_digest_keeps_everything(monkeypatch, broken) -> None:
    """An extract with nothing behind it cannot be cited, and pages with no
    extract leave nothing to answer from."""
    monkeypatch.setattr(settings, "context_mode", "digest")
    _answers(monkeypatch, WRITE_EXTRACT, broken)

    context = context_select.narrow("вопрос", HITS)

    assert context.chunks == HITS
    assert context.digest is None
