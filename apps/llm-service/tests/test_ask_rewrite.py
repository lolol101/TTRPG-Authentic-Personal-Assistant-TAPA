"""The /ask side of rewriting: what is actually searched.

What this protects: every rule the question names is searched in English;
the question as restated without the dialogue is the safety-net search, so
a new topic is not searched together with the old one; and when nothing
usable comes back, the request keeps the glued search it always had. A
sheet request — already split into English area queries by the planner —
must not pay for a second rewriting call on top.
"""

from app.api import ask as ask_api
from app.core.config import settings
from app.core.query_rewrite import Rewrite
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


def _rewrites_to(monkeypatch, rewrite: Rewrite) -> list[tuple]:
    calls: list[tuple] = []

    def _fake(question, history):
        calls.append((question, history))
        return rewrite

    monkeypatch.setattr(ask_api, "rewrite_question", _fake)
    return calls


SPELLS_TALK = [
    {"role": "user", "text": "Подбери заклинания контроля, замедления"},
    {"role": "assistant", "text": "Slow — заклинание 3-го круга..."},
]


def test_english_queries_first_then_the_restated_question(monkeypatch) -> None:
    queries = _record_queries(monkeypatch)
    _rewrites_to(monkeypatch, Rewrite("Что делает Устрашение?", ["Demoralize action"]))

    retrieved, _, _, _ = ask_api._prepare(_payload())

    assert queries == ["Demoralize action", "Что делает Устрашение?"]
    assert retrieved[0]["metadata"]["title"] == "Demoralize action"


def test_a_new_topic_is_not_searched_with_the_old_one(monkeypatch) -> None:
    """Replayed live: glued to the previous question, "Что я могу купить?"
    found Slow and Stagnate Time and was answered as a question about
    buying spells, 3 times of 3."""
    queries = _record_queries(monkeypatch)
    _rewrites_to(monkeypatch, Rewrite("Что я могу купить на своём уровне?", ["buying items"]))

    ask_api._prepare(_payload(question="Что я могу купить на своем уровне?", history=SPELLS_TALK))

    assert all("заклинания" not in query for query in queries)
    assert queries == ["buying items", "Что я могу купить на своём уровне?"]


def test_a_follow_up_is_searched_with_its_subject_filled_in(monkeypatch) -> None:
    queries = _record_queries(monkeypatch)
    calls = _rewrites_to(
        monkeypatch, Rewrite("Можно ли схватить цель в тяжёлой броне?", ["Grapple"])
    )

    ask_api._prepare(
        _payload(
            question="А если он в тяжёлой броне?",
            history=[{"role": "user", "text": "Что делает действие Захват?"}],
        )
    )

    assert calls[0][0] == "А если он в тяжёлой броне?"
    assert [turn.text for turn in calls[0][1]] == ["Что делает действие Захват?"]
    assert queries[-1] == "Можно ли схватить цель в тяжёлой броне?"


def test_without_a_restatement_the_old_glued_search_stays(monkeypatch) -> None:
    """A rewrite that failed must leave the request exactly where it was —
    and for a follow-up, that is the question glued to the previous one."""
    queries = _record_queries(monkeypatch)
    _rewrites_to(monkeypatch, Rewrite())

    ask_api._prepare(
        _payload(
            question="А если он в тяжёлой броне?",
            history=[{"role": "user", "text": "Что делает действие Захват?"}],
        )
    )

    assert queries == ["Что делает действие Захват?\nА если он в тяжёлой броне?"]


def test_the_same_page_found_by_both_phrasings_appears_once(monkeypatch) -> None:
    monkeypatch.setattr(
        ask_api, "retrieve", lambda query, k, ruleset=None, categories=None: [_hit("Demoralize")]
    )
    monkeypatch.setattr(ask_api, "plan_for", lambda question: [])
    _rewrites_to(monkeypatch, Rewrite("Что делает Устрашение?", ["Demoralize action"]))

    retrieved, _, _, _ = ask_api._prepare(_payload())

    assert len(retrieved) == 1


def test_the_answer_prompt_names_the_restated_question(monkeypatch) -> None:
    """The dialogue informs how the question is read; it must not replace
    it — so the restatement travels next to the player's own words."""
    _record_queries(monkeypatch)
    _rewrites_to(monkeypatch, Rewrite("Что я могу купить на своём уровне?", []))

    _, messages, _, _ = ask_api._prepare(
        _payload(question="Что я могу купить?", history=SPELLS_TALK)
    )

    assert "Вопрос игрока: Что я могу купить?" in messages[-1]["content"]
    assert "означает: Что я могу купить на своём уровне?" in messages[-1]["content"]


def test_rewriting_can_be_turned_off(monkeypatch) -> None:
    """The extra completion is real latency on a CPU box; the plain single
    search has to stay one config flag away."""
    queries = _record_queries(monkeypatch)
    monkeypatch.setattr(settings, "retrieval_rewrite_query", False)

    def _must_not_run(question, history):
        raise AssertionError("rewriting is off; no provider call may be made")

    monkeypatch.setattr(ask_api, "rewrite_question", _must_not_run)

    ask_api._prepare(_payload())

    assert queries == ["Что делает действие Устрашение?"]


def test_a_split_sheet_request_is_not_rewritten(monkeypatch) -> None:
    """The planner already writes its area queries in English, so a second
    call would spend latency restating what it just said."""
    queries = _record_queries(monkeypatch)
    monkeypatch.setattr(
        ask_api, "plan_for", lambda question: [PlanStep(area="class", query="rogue features")]
    )

    def _must_not_run(question, history):
        raise AssertionError("a planned request needs no rewriting")

    monkeypatch.setattr(ask_api, "rewrite_question", _must_not_run)

    ask_api._prepare(
        _payload(
            question="Собери плута",
            allow_sheet_edits=True,
            character_context="Лист: пустой",
        )
    )

    assert queries == ["rogue features"]
