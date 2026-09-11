"""The ask endpoints seen from a chat: what reaches the model, what is kept."""

import json
from contextlib import contextmanager

import httpx

from app.api import llm
from app.core import chat_store


def _auth_headers(client, email="alice@example.com", password="correct-horse-battery-staple"):
    client.post("/auth/register", json={"email": email, "password": password})
    token = client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


class _FakeAskResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


def _stub_ask(monkeypatch, captured: dict | None = None, payload: dict | None = None):
    def _fake_post(url, json, timeout):
        if captured is not None:
            captured["json"] = json
        return _FakeAskResponse(
            200,
            payload or {"answer": "Захват обездвиживает цель.", "sources": []},
        )

    monkeypatch.setattr(llm.httpx, "post", _fake_post)


class _FakeStream:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self.status_code = 200
        self.text = ""

    def iter_lines(self):
        yield from self._lines

    def read(self) -> None:
        return None


def _stub_stream(monkeypatch, lines: list[str], captured: dict | None = None):
    @contextmanager
    def _fake(method, url, json=None, timeout=None):
        if captured is not None:
            captured["json"] = json
        yield _FakeStream(lines)

    monkeypatch.setattr(llm.httpx, "stream", _fake)


def _frames(response) -> dict[str, dict]:
    return {
        name: json.loads(data)
        for name, data in llm._iter_sse_frames(iter(response.text.splitlines()))
    }


def _new_chat(client, headers, **fields) -> dict:
    return client.post("/chats", json=fields, headers=headers).json()


def _messages(client, headers, chat_id: int) -> list[dict]:
    return client.get(f"/chats/{chat_id}/messages", headers=headers).json()


def test_the_chat_so_far_is_sent_to_the_model(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    chat = _new_chat(client, headers)
    captured: dict = {}
    _stub_ask(monkeypatch, captured)

    client.post(
        "/llm/ask",
        json={"question": "Как работает Захват?", "chat_id": chat["id"]},
        headers=headers,
    )
    client.post(
        "/llm/ask", json={"question": "А если в броне?", "chat_id": chat["id"]}, headers=headers
    )

    assert captured["json"]["history"] == [
        {"role": "user", "text": "Как работает Захват?"},
        {"role": "assistant", "text": "Захват обездвиживает цель."},
    ]


def test_a_question_outside_a_chat_still_works_and_is_not_stored(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    captured: dict = {}
    _stub_ask(monkeypatch, captured)

    response = client.post("/llm/ask", json={"question": "Что делает Удар?"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["message_id"] is None
    assert captured["json"]["history"] == []


def test_the_turn_is_kept_with_its_sources(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    chat = _new_chat(client, headers)
    _stub_ask(
        monkeypatch,
        payload={
            "answer": "Захват обездвиживает цель.",
            "sources": [{"title": "Захват", "url": "https://pf2.ru/actions/grapple"}],
        },
    )

    client.post(
        "/llm/ask",
        json={"question": "Как работает Захват?", "chat_id": chat["id"]},
        headers=headers,
    )

    stored = _messages(client, headers, chat["id"])
    assert [message["role"] for message in stored] == ["user", "assistant"]
    assert stored[1]["sources"][0]["title"] == "Захват"


def test_a_failed_answer_leaves_no_half_turn_behind(client, monkeypatch) -> None:
    """A stranded question would be asked a second time on the retry."""
    headers = _auth_headers(client)
    chat = _new_chat(client, headers)

    def _raise(url, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(llm.httpx, "post", _raise)

    response = client.post(
        "/llm/ask", json={"question": "вопрос", "chat_id": chat["id"]}, headers=headers
    )

    assert response.status_code == 502
    assert _messages(client, headers, chat["id"]) == []


def test_a_streamed_answer_is_stored_once_it_finishes(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    chat = _new_chat(client, headers)
    _stub_stream(
        monkeypatch,
        [
            "event: sources",
            'data: [{"title": "Захват", "url": "https://pf2.ru/actions/grapple"}]',
            "",
            "event: delta",
            'data: {"text": "Захват "}',
            "",
            "event: delta",
            'data: {"text": "обездвиживает."}',
            "",
            "event: done",
            'data: {"proposed_changes": [], "provider": "ollama-local", "memory": {"used": 0}}',
            "",
        ],
    )

    response = client.post(
        "/llm/ask/stream",
        json={"question": "Как работает Захват?", "chat_id": chat["id"]},
        headers=headers,
    )

    assert response.status_code == 200
    stored = _messages(client, headers, chat["id"])
    assert [message["text"] for message in stored] == [
        "Как работает Захват?",
        "Захват обездвиживает.",
    ]
    assert stored[1]["sources"][0]["title"] == "Захват"


def test_the_stored_answer_is_named_in_the_done_frame(client, monkeypatch) -> None:
    """The page needs the id to record that the sheet edits were applied."""
    headers = _auth_headers(client)
    chat = _new_chat(client, headers)
    _stub_stream(
        monkeypatch,
        ["event: done", 'data: {"proposed_changes": [], "provider": "p", "memory": {}}', ""],
    )

    response = client.post(
        "/llm/ask/stream", json={"question": "вопрос", "chat_id": chat["id"]}, headers=headers
    )

    assert _frames(response)["done"]["message_id"] is not None


def test_how_much_was_remembered_reaches_the_page(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    chat = _new_chat(client, headers)
    _stub_stream(
        monkeypatch,
        [
            "event: done",
            'data: {"proposed_changes": [], "provider": "p", '
            '"memory": {"used": 2, "dropped": 4, "tokens": 900, "budget": 3000}}',
            "",
        ],
    )

    response = client.post(
        "/llm/ask/stream", json={"question": "вопрос", "chat_id": chat["id"]}, headers=headers
    )

    assert _frames(response)["done"]["memory"] == {
        "used": 2,
        "dropped": 4,
        "tokens": 900,
        "budget": 3000,
    }


def test_the_chat_decides_the_character_not_the_question(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    mine = client.post("/characters", json={"name": "Рэм", "hp_max": 40}, headers=headers).json()
    other = client.post("/characters", json={"name": "Сила"}, headers=headers).json()
    chat = _new_chat(client, headers, character_id=mine["id"])
    captured: dict = {}
    _stub_ask(monkeypatch, captured)

    client.post(
        "/llm/ask",
        json={"question": "вопрос", "chat_id": chat["id"], "character_id": other["id"]},
        headers=headers,
    )

    assert "Рэм" in captured["json"]["character_context"]
    assert "Сила" not in captured["json"]["character_context"]


def test_the_chats_ruleset_is_used_when_it_has_no_character(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    chat = _new_chat(client, headers, ruleset="dnd5e")
    captured: dict = {}
    _stub_ask(monkeypatch, captured)

    client.post("/llm/ask", json={"question": "вопрос", "chat_id": chat["id"]}, headers=headers)

    assert captured["json"]["ruleset"] == "dnd5e"


def test_another_users_chat_cannot_be_continued(client, monkeypatch) -> None:
    alice = _auth_headers(client)
    chat = _new_chat(client, alice)
    bob = _auth_headers(client, email="bob@example.com")
    _stub_ask(monkeypatch)

    response = client.post(
        "/llm/ask", json={"question": "вопрос", "chat_id": chat["id"]}, headers=bob
    )

    assert response.status_code == 404


def test_an_oversized_question_is_refused_before_it_reaches_the_model(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    monkeypatch.setattr(chat_store.settings, "max_message_chars", 10)

    def _must_not_be_called(url, json, timeout):
        raise AssertionError("the provider should not have been called")

    monkeypatch.setattr(llm.httpx, "post", _must_not_be_called)

    response = client.post("/llm/ask", json={"question": "вопрос" * 10}, headers=headers)

    assert response.status_code == 413


def test_a_full_chat_says_so_instead_of_growing_forever(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    chat = _new_chat(client, headers)
    _stub_ask(monkeypatch)
    client.post("/llm/ask", json={"question": "первый", "chat_id": chat["id"]}, headers=headers)
    monkeypatch.setattr(chat_store.settings, "max_messages_per_chat", 2)

    response = client.post(
        "/llm/ask", json={"question": "второй", "chat_id": chat["id"]}, headers=headers
    )

    assert response.status_code == 409
    assert "новый чат" in response.json()["detail"]
