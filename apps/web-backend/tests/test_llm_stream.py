import json
from contextlib import contextmanager

import httpx

from app.api import llm
from app.api.llm import _iter_sse_frames


def _auth_headers(client, email="alice@example.com", password="correct-horse-battery-staple"):
    client.post("/auth/register", json={"email": email, "password": password})
    token = client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


class _FakeStream:
    def __init__(self, lines: list[str], status_code: int = 200) -> None:
        self._lines = lines
        self.status_code = status_code
        self.text = ""

    def iter_lines(self):
        yield from self._lines

    def read(self) -> None:
        return None


def _stub_stream(monkeypatch, lines: list[str], status_code: int = 200, captured=None):
    @contextmanager
    def _fake(method, url, json=None, timeout=None):
        if captured is not None:
            captured["url"] = url
            captured["json"] = json
        yield _FakeStream(lines, status_code)

    monkeypatch.setattr(llm.httpx, "stream", _fake)


def _frames(response) -> list[tuple[str, dict]]:
    parsed = []
    for name, data in _iter_sse_frames(iter(response.text.splitlines())):
        parsed.append((name, json.loads(data)))
    return parsed


def test_sse_parser_reassembles_events() -> None:
    lines = ["event: delta", 'data: {"text": "раз"}', "", "event: done", "data: {}", ""]

    assert list(_iter_sse_frames(iter(lines))) == [
        ("delta", '{"text": "раз"}'),
        ("done", "{}"),
    ]


def test_sse_parser_yields_a_trailing_frame_without_blank_line() -> None:
    assert list(_iter_sse_frames(iter(["event: done", "data: {}"]))) == [("done", "{}")]


def test_stream_requires_authentication(client) -> None:
    response = client.post("/llm/ask/stream", json={"question": "вопрос"})

    assert response.status_code == 401


def test_stream_passes_sources_and_text_through(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    _stub_stream(
        monkeypatch,
        [
            "event: sources",
            'data: [{"title": "Захват", "url": "https://pf2.ru/actions/grapple",'
            ' "source_book": ""}]',
            "",
            "event: delta",
            'data: {"text": "Захват "}',
            "",
            "event: delta",
            'data: {"text": "позволяет"}',
            "",
            "event: done",
            'data: {"proposed_changes": [], "provider": "openrouter"}',
            "",
        ],
    )

    response = client.post("/llm/ask/stream", json={"question": "Что делает Захват?"}, headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = _frames(response)
    assert frames[0][0] == "sources"
    assert frames[0][1][0]["title"] == "Захват"
    assert [f[1]["text"] for f in frames if f[0] == "delta"] == ["Захват ", "позволяет"]


def test_stream_vets_proposed_changes_against_the_whitelist(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    character_id = client.post(
        "/characters", json={"name": "Рэм", "hp_current": 60, "hp_max": 73}, headers=headers
    ).json()["id"]
    _stub_stream(
        monkeypatch,
        [
            "event: done",
            'data: {"proposed_changes": ['
            '{"path": "hp_current", "value": 80, "reason": "лечение"},'
            '{"path": "owner_id", "value": 2, "reason": "нельзя"}'
            '], "provider": "test"}',
            "",
        ],
    )

    response = client.post(
        "/llm/ask/stream",
        json={"question": "вылечи меня", "character_id": character_id},
        headers=headers,
    )

    done = [payload for name, payload in _frames(response) if name == "done"][0]
    assert [change["path"] for change in done["proposed_changes"]] == ["hp_current"]
    assert done["proposed_changes"][0]["before"] == 60
    assert len(done["rejected_changes"]) == 1


def test_stream_accepts_a_column_the_model_prefixed_with_sheet_data(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    character_id = client.post(
        "/characters", json={"name": "Рэм", "hp_current": 60, "hp_max": 73}, headers=headers
    ).json()["id"]
    _stub_stream(
        monkeypatch,
        [
            "event: done",
            'data: {"proposed_changes": ['
            '{"path": "sheet_data.hp_max", "value": 93, "reason": "+20"}], "provider": "t"}',
            "",
        ],
    )

    response = client.post(
        "/llm/ask/stream",
        json={"question": "увеличь хп на 20", "character_id": character_id},
        headers=headers,
    )

    done = [payload for name, payload in _frames(response) if name == "done"][0]
    assert done["proposed_changes"][0]["path"] == "hp_max"
    assert done["rejected_changes"] == []


def test_stream_refuses_a_character_owned_by_someone_else(client, monkeypatch) -> None:
    alice = _auth_headers(client, email="alice@example.com")
    bob = _auth_headers(client, email="bob@example.com")
    character_id = client.post("/characters", json={"name": "PC"}, headers=alice).json()["id"]
    _stub_stream(monkeypatch, [])

    response = client.post(
        "/llm/ask/stream",
        json={"question": "вопрос", "character_id": character_id},
        headers=bob,
    )

    assert response.status_code == 404


def test_stream_reports_an_unreachable_service_as_an_event(client, monkeypatch) -> None:
    headers = _auth_headers(client)

    @contextmanager
    def _raise(method, url, json=None, timeout=None):
        raise httpx.ConnectError("connection refused")
        yield  # pragma: no cover

    monkeypatch.setattr(llm.httpx, "stream", _raise)

    response = client.post("/llm/ask/stream", json={"question": "вопрос"}, headers=headers)

    # The status line is sent before the failure is known, so the error has to
    # arrive inside the stream rather than as an HTTP status.
    assert response.status_code == 200
    error = [payload for name, payload in _frames(response) if name == "error"][0]
    assert error["status"] == 502
