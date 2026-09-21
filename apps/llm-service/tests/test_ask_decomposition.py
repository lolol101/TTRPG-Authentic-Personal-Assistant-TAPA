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

    def _fake_retrieve(query, k, ruleset=None, categories=None):
        queries.append(query)
        return [_hit("Grapple")]

    monkeypatch.setattr(ask_api, "retrieve", _fake_retrieve)
    monkeypatch.setattr(ask_api, "plan_for", lambda question: [])
    monkeypatch.setattr(ask_api, "search_queries_for", lambda question: [])

    retrieved, _, _ = ask_api._prepare(
        _payload(question="Что делает Grapple?", allow_sheet_edits=False, character_context=None)
    )

    assert len(queries) == 1
    assert len(retrieved) == 1


def test_a_sheet_request_searches_once_per_area(monkeypatch) -> None:
    queries: list[str] = []

    def _fake_retrieve(query, k, ruleset=None, categories=None):
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
    monkeypatch.setattr(
        ask_api, "retrieve", lambda query, k, ruleset=None, categories=None: [_hit("Rogue")]
    )
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
    monkeypatch.setattr(
        ask_api, "retrieve", lambda query, k, ruleset=None, categories=None: [_hit("Whatever")]
    )
    monkeypatch.setattr(ask_api, "plan_for", lambda question: [])
    monkeypatch.setattr(ask_api, "search_queries_for", lambda question: [])

    retrieved, messages, _ = ask_api._prepare(_payload())

    assert len(retrieved) == 1
    assert messages


def test_each_area_search_is_restricted_to_that_areas_sections(monkeypatch) -> None:
    """The point of knowing the area: it narrows the search, not just the
    wording. Before this the area only changed the query string, so all six
    searches still ranked against the whole corpus — two thirds of which is
    feats and equipment."""
    seen: list[tuple[str, tuple | None]] = []

    def _fake_retrieve(query, k, ruleset=None, categories=None):
        seen.append((query, categories))
        return [_hit(f"hit for {query}")]

    monkeypatch.setattr(ask_api, "retrieve", _fake_retrieve)
    monkeypatch.setattr(ask_api.settings, "retrieval_filter_by_section", True)
    monkeypatch.setattr(
        ask_api,
        "plan_for",
        lambda question: [
            PlanStep(area="class", query="rogue features"),
            PlanStep(area="feats", query="rogue level 1 feats"),
            PlanStep(area="skills", query="trained skills"),
        ],
    )

    ask_api._prepare(_payload())

    assert seen == [
        ("rogue features", ("classes", "class-features")),
        ("rogue level 1 feats", ("feats",)),
        # Unmapped on purpose — nothing in the corpus to narrow to.
        ("trained skills", None),
    ]


def test_the_section_filter_can_be_turned_off(monkeypatch) -> None:
    """Retrieval parameters go through config, so the old whole-index
    behaviour stays one setting away — see .claude/rules/ml-system-design.md."""
    seen: list[tuple | None] = []

    def _fake_retrieve(query, k, ruleset=None, categories=None):
        seen.append(categories)
        return [_hit(query)]

    monkeypatch.setattr(ask_api, "retrieve", _fake_retrieve)
    monkeypatch.setattr(ask_api.settings, "retrieval_filter_by_section", False)
    monkeypatch.setattr(
        ask_api, "plan_for", lambda question: [PlanStep(area="class", query="rogue features")]
    )

    ask_api._prepare(_payload())

    assert seen == [None]
