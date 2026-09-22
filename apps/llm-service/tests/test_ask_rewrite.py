"""The /ask side of rewriting: search every named concept, keep the original.

What this protects: the rewrite is an addition, never a replacement. A
question whose rewrite missed must still be served by the search it would
have had, a question naming two rules must be searched for both, and a
sheet request — already split into English area queries by the planner —
must not pay for a second rewriting call on top.
"""

from app.api import ask as ask_api
from app.core.config import settings
from app.core.sheet_plan import PlanStep


def _hit(title: str) -> dict:
    return {
        "id": title,
        "text": f"{title} rules text",
        "metadata": {"title": title, "url": f"https://example.invalid/{title}", "source_book": "X"},
        "distance": 0.5,
    }


def _payload(**overrides):
    from app.schemas.ask import AskRequest

    body = {"question": "Что делает действие Устрашение?", "k": 5}
    body.update(overrides)
    return AskRequest(**body)


def _record_queries(monkeypatch) -> list[str]:
    queries: list[str] = []

    def _fake_retrieve(query, k, ruleset=None, categories=None):
        queries.append(query)
        return [_hit(query)]

    monkeypatch.setattr(ask_api, "retrieve", _fake_retrieve)
    monkeypatch.setattr(ask_api, "plan_for", lambda question: [])
    return queries


def test_both_phrasings_are_searched(monkeypatch) -> None:
    queries = _record_queries(monkeypatch)
    monkeypatch.setattr(ask_api, "search_queries_for", lambda question: ["Demoralize action"])

    retrieved, _, _, _ = ask_api._prepare(_payload())

    assert queries == ["Demoralize action", "Что делает действие Устрашение?"]
    assert len(retrieved) == 2


def test_every_named_concept_gets_its_own_search(monkeypatch) -> None:
    """The measured failure this exists for: one query for a two-rule
    question found 8 of 12 concepts across six questions, one query per
    concept found 11 — the miss was the concept the rewrite dropped, not
    a page ranked too deep."""
    queries = _record_queries(monkeypatch)
    monkeypatch.setattr(
        ask_api,
        "search_queries_for",
        lambda question: ["Grapple action", "Frightened condition"],
    )

    ask_api._prepare(_payload(question="Могу ли я схватить, если напуган?"))

    assert queries == [
        "Grapple action",
        "Frightened condition",
        "Могу ли я схватить, если напуган?",
    ]


def test_the_english_hits_come_first(monkeypatch) -> None:
    """Measured on this index, the English phrasing is the one that ranks the
    answering page in the top few — and the model reads the front of its
    context most closely."""
    queries = _record_queries(monkeypatch)
    monkeypatch.setattr(ask_api, "search_queries_for", lambda question: ["Demoralize action"])

    retrieved, _, _, _ = ask_api._prepare(_payload())

    assert retrieved[0]["metadata"]["title"] == "Demoralize action"
    assert queries[0] == "Demoralize action"


def test_without_a_rewrite_the_question_is_searched_alone(monkeypatch) -> None:
    queries = _record_queries(monkeypatch)
    monkeypatch.setattr(ask_api, "search_queries_for", lambda question: [])

    ask_api._prepare(_payload())

    assert queries == ["Что делает действие Устрашение?"]


def test_the_same_page_found_by_both_phrasings_appears_once(monkeypatch) -> None:
    monkeypatch.setattr(
        ask_api, "retrieve", lambda query, k, ruleset=None, categories=None: [_hit("Demoralize")]
    )
    monkeypatch.setattr(ask_api, "plan_for", lambda question: [])
    monkeypatch.setattr(ask_api, "search_queries_for", lambda question: ["Demoralize action"])

    retrieved, _, _, _ = ask_api._prepare(_payload())

    assert len(retrieved) == 1


def test_rewriting_can_be_turned_off(monkeypatch) -> None:
    """The extra completion is real latency on a CPU box; the plain single
    search has to stay one config flag away."""
    queries = _record_queries(monkeypatch)
    monkeypatch.setattr(settings, "retrieval_rewrite_query", False)

    def _must_not_run(question):
        raise AssertionError("rewriting is off; no provider call may be made")

    monkeypatch.setattr(ask_api, "search_queries_for", _must_not_run)

    ask_api._prepare(_payload())

    assert queries == ["Что делает действие Устрашение?"]


def test_a_split_sheet_request_is_not_rewritten(monkeypatch) -> None:
    """The planner already writes its area queries in English, so a second
    call would spend latency restating what it just said."""
    queries = _record_queries(monkeypatch)
    monkeypatch.setattr(
        ask_api, "plan_for", lambda question: [PlanStep(area="class", query="rogue features")]
    )

    def _must_not_run(question):
        raise AssertionError("a planned request needs no rewriting")

    monkeypatch.setattr(ask_api, "search_queries_for", _must_not_run)

    ask_api._prepare(
        _payload(
            question="Собери плута",
            allow_sheet_edits=True,
            character_context="Лист: пустой",
        )
    )

    assert queries == ["rogue features"]


def test_the_follow_up_context_is_rewritten_too(monkeypatch) -> None:
    """A follow-up is embedded together with the question before it; the
    rewrite has to see that same text or it renames the wrong question."""
    _record_queries(monkeypatch)
    seen: list[str] = []
    monkeypatch.setattr(
        ask_api,
        "search_queries_for",
        lambda question: seen.append(question) or ["heavy armour"],
    )

    ask_api._prepare(
        _payload(
            question="А если он в тяжёлой броне?",
            history=[{"role": "user", "text": "Что делает действие Захват?"}],
        )
    )

    assert "Захват" in seen[0]
    assert "тяжёлой броне" in seen[0]
