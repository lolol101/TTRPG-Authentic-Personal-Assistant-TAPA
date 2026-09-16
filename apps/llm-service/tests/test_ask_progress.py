"""Progress events, so a long request shows what it is doing.

A sheet request now plans, then searches once per area, then generates; an
ordinary question is rewritten before it is searched. Either way that is
seconds of work before the first word of the answer exists. A spinner for
that says only "still alive"; naming the stage says what is happening and,
for a split request, how much of it is left.
"""

import json

from fastapi.testclient import TestClient

from app.api import ask as ask_api
from app.core.llm_provider import Completion
from app.core.sheet_plan import PlanStep
from app.main import app

client = TestClient(app)


def _hit(title: str) -> dict:
    return {
        "id": title,
        "text": f"{title} text",
        "metadata": {"title": title, "url": f"https://example.invalid/{title}", "source_book": ""},
        "distance": 0.4,
    }


def _events(body: dict) -> list[tuple[str, dict]]:
    with client.stream("POST", "/ask/stream", json=body) as response:
        raw = "".join(response.iter_text())

    events: list[tuple[str, dict]] = []
    name = None
    for line in raw.splitlines():
        if line.startswith("event:"):
            name = line.removeprefix("event:").strip()
        elif line.startswith("data:") and name:
            events.append((name, json.loads(line.removeprefix("data:").strip())))
    return events


def _stub_stream(monkeypatch) -> None:
    def _fake_stream(messages, tools=None):
        yield "ответ"
        yield Completion(text="ответ", provider="test")

    monkeypatch.setattr(ask_api, "stream", _fake_stream)


def test_a_plain_question_reports_rewriting_searching_then_generating(monkeypatch) -> None:
    monkeypatch.setattr(ask_api, "retrieve", lambda *a, **k: [_hit("Grapple")])
    monkeypatch.setattr(ask_api, "plan_for", lambda question: [])
    monkeypatch.setattr(ask_api, "rewrite_for_search", lambda question: "Grapple action")
    _stub_stream(monkeypatch)

    events = _events({"question": "Что такое Grapple?"})
    stages = [data["stage"] for name, data in events if name == "stage"]

    assert stages == ["rewriting", "searching", "generating"]


def test_a_split_request_names_each_area_as_it_is_searched(monkeypatch) -> None:
    """The point of the indicator: six searches look identical from outside,
    so say which one is running and how many there are."""
    monkeypatch.setattr(ask_api, "retrieve", lambda *a, **k: [_hit("X")])
    monkeypatch.setattr(ask_api, "rewrite_for_search", lambda question: None)
    monkeypatch.setattr(
        ask_api,
        "plan_for",
        lambda question: [
            PlanStep(area="ancestry", query="elf"),
            PlanStep(area="equipment", query="gear"),
        ],
    )
    _stub_stream(monkeypatch)

    events = _events(
        {
            "question": "Собери плута",
            "allow_sheet_edits": True,
            "character_context": "Лист: пустой",
        }
    )
    stages = [data for name, data in events if name == "stage"]

    assert [s["stage"] for s in stages] == ["planning", "searching", "searching", "generating"]
    assert [s.get("area") for s in stages[1:3]] == ["ancestry", "equipment"]
    assert [s.get("index") for s in stages[1:3]] == [1, 2]
    assert all(s.get("total") == 2 for s in stages[1:3])


def test_progress_comes_before_the_answer_not_after(monkeypatch) -> None:
    """Arriving after the text would make it a log, not an indicator."""
    monkeypatch.setattr(ask_api, "retrieve", lambda *a, **k: [_hit("Grapple")])
    monkeypatch.setattr(ask_api, "plan_for", lambda question: [])
    monkeypatch.setattr(ask_api, "rewrite_for_search", lambda question: None)
    _stub_stream(monkeypatch)

    names = [name for name, _ in _events({"question": "Что такое Grapple?"})]

    assert names.index("stage") < names.index("delta")
    assert names.index("sources") < names.index("delta")


def test_the_answer_still_arrives_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(ask_api, "retrieve", lambda *a, **k: [_hit("Grapple")])
    monkeypatch.setattr(ask_api, "plan_for", lambda question: [])
    monkeypatch.setattr(ask_api, "rewrite_for_search", lambda question: None)
    _stub_stream(monkeypatch)

    events = _events({"question": "Что такое Grapple?"})

    assert [data["text"] for name, data in events if name == "delta"] == ["ответ"]
    assert any(name == "done" for name, _ in events)
    assert any(name == "sources" for name, _ in events)
