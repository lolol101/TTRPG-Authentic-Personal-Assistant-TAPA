"""The /ask side of splitting a sheet request: one search per area, merged.

What this protects: an ordinary rules question must keep costing exactly one
retrieval, and a sheet request must stop being served by a single k=5 search
that cannot cover a whole character.
"""

from app.api import ask as ask_api
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

    body = {
        "question": "Собери плута 1 уровня",
        "k": 5,
        "allow_sheet_edits": True,
        "character_context": "Лист персонажа: пустой",
    }
    body.update(overrides)
    return AskRequest(**body)


def test_a_plain_question_makes_exactly_one_retrieval(monkeypatch) -> None:
    queries: list[str] = []

    def _fake_retrieve(query, k, ruleset=None):
        queries.append(query)
        return [_hit("Grapple")]

    monkeypatch.setattr(ask_api, "retrieve", _fake_retrieve)
    monkeypatch.setattr(ask_api, "plan_for", lambda question: [])
    monkeypatch.setattr(ask_api, "rewrite_for_search", lambda question: None)

    retrieved, _, _ = ask_api._prepare(
        _payload(question="Что делает Grapple?", allow_sheet_edits=False, character_context=None)
    )

    assert len(queries) == 1
    assert len(retrieved) == 1


def test_a_sheet_request_searches_once_per_area(monkeypatch) -> None:
    queries: list[str] = []

    def _fake_retrieve(query, k, ruleset=None):
        queries.append(query)
        return [_hit(f"hit for {query}")]

    monkeypatch.setattr(ask_api, "retrieve", _fake_retrieve)
    monkeypatch.setattr(
        ask_api,
        "plan_for",
        lambda question: [
            PlanStep(area="ancestry", query="elf heritage"),
            PlanStep(area="class", query="rogue features"),
            PlanStep(area="equipment", query="starting gear"),
        ],
    )

    retrieved, _, _ = ask_api._prepare(_payload())

    assert queries == ["elf heritage", "rogue features", "starting gear"]
    assert len(retrieved) == 3


def test_the_same_rule_found_twice_appears_once(monkeypatch) -> None:
    """Areas overlap — a rogue's gear and a rogue's class both surface the
    same page — and paying context for it twice buys nothing."""
    monkeypatch.setattr(ask_api, "retrieve", lambda query, k, ruleset=None: [_hit("Rogue")])
    monkeypatch.setattr(
        ask_api,
        "plan_for",
        lambda question: [
            PlanStep(area="class", query="rogue"),
            PlanStep(area="feats", query="rogue feats"),
        ],
    )

    retrieved, _, _ = ask_api._prepare(_payload())

    assert len(retrieved) == 1


def test_planning_never_blocks_the_answer(monkeypatch) -> None:
    """If planning is unavailable the request must still be answered the
    old way rather than failing."""
    monkeypatch.setattr(ask_api, "retrieve", lambda query, k, ruleset=None: [_hit("Whatever")])
    monkeypatch.setattr(ask_api, "plan_for", lambda question: [])
    monkeypatch.setattr(ask_api, "rewrite_for_search", lambda question: None)

    retrieved, messages, _ = ask_api._prepare(_payload())

    assert len(retrieved) == 1
    assert messages
