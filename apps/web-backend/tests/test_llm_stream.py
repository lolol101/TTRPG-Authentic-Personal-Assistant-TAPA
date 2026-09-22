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

    response = client.post(
        "/llm/ask/stream", json={"question": "Что делает Захват?"}, headers=headers
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = _frames(response)
    assert frames[0][0] == "sources"
    assert frames[0][1][0]["title"] == "Захват"
    assert [f[1]["text"] for f in frames if f[0] == "delta"] == ["Захват ", "позволяет"]


def _stub_retry_post(monkeypatch, proposals: list[dict], captured: dict | None = None):
    """Stubs the plain (non-streaming) call the retry leg makes to llm-service."""

    def _fake_post(url, json, timeout):
        if captured is not None:
            captured["json"] = json
        return _FakePostResponse(200, {"answer": "", "sources": [], "proposed_changes": proposals})

    monkeypatch.setattr(llm.httpx, "post", _fake_post)


class _FakePostResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


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
    # owner_id stays rejected however the model tries again — the retry leg
    # must not go out over a real socket in a test.
    _stub_retry_post(monkeypatch, [{"path": "owner_id", "value": 2}])

    response = client.post(
        "/llm/ask/stream",
        json={"question": "вылечи меня", "character_id": character_id},
        headers=headers,
    )

    done = [payload for name, payload in _frames(response) if name == "done"][0]
    assert [change["path"] for change in done["proposed_changes"]] == ["hp_current"]
    assert done["proposed_changes"][0]["before"] == 60
    assert len(done["rejected_changes"]) == 1


def test_stream_retries_a_rejected_proposal_with_feedback(client, monkeypatch) -> None:
    """The streamed answer itself is untouched — only the tool call is
    corrected, silently, before the "done" event carries the result."""
    headers = _auth_headers(client)
    character_id = client.post("/characters", json={"name": "Рэм"}, headers=headers).json()["id"]
    _stub_stream(
        monkeypatch,
        [
            "event: delta",
            'data: {"text": "Собрал."}',
            "",
            "event: done",
            'data: {"proposed_changes": [{"path": "sheet_data.made_up_field", "value": "x"}],'
            ' "provider": "test"}',
            "",
        ],
    )
    captured: dict = {}
    _stub_retry_post(monkeypatch, [{"path": "ancestry", "value": "Человек"}], captured)

    response = client.post(
        "/llm/ask/stream",
        json={"question": "Собери персонажа", "character_id": character_id},
        headers=headers,
    )

    frames = _frames(response)
    assert [f[1]["text"] for f in frames if f[0] == "delta"] == ["Собрал."]
    done = [payload for name, payload in frames if name == "done"][0]
    assert [change["path"] for change in done["proposed_changes"]] == ["ancestry"]
    assert done["rejected_changes"] == []
    assert "sheet_data.made_up_field" in captured["json"]["retry_feedback"]
    assert captured["json"]["history"][-1] == {"role": "assistant", "text": "Собрал."}


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


def test_stream_passes_the_weak_event_through_untouched(client, monkeypatch) -> None:
    """No explicit handling needed in the relay — see _iter_sse_frames: only
    "done" is rebuilt from named fields, everything else passes as-is."""
    headers = _auth_headers(client)
    _stub_stream(
        monkeypatch,
        [
            "event: sources",
            "data: []",
            "",
            "event: weak",
            'data: {"weak": true}',
            "",
            "event: done",
            'data: {"proposed_changes": [], "provider": "openrouter"}',
            "",
        ],
    )

    response = client.post("/llm/ask/stream", json={"question": "борщ"}, headers=headers)

    frames = _frames(response)
    assert ("weak", {"weak": True}) in frames
