import httpx

from app.api import llm


def _auth_headers(client, email="alice@example.com", password="correct-horse-battery-staple"):
    client.post("/auth/register", json={"email": email, "password": password})
    token = client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_ping_returns_llm_service_health(client, monkeypatch) -> None:
    monkeypatch.setattr(
        llm.httpx,
        "get",
        lambda url, timeout: _FakeResponse({"status": "ok", "service": "llm-service"}),
    )

    response = client.get("/llm/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "llm-service"}


def test_ping_returns_502_when_llm_service_unreachable(client, monkeypatch) -> None:
    def _raise(url, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(llm.httpx, "get", _raise)

    response = client.get("/llm/ping")

    assert response.status_code == 502


class _FakeAskResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


def _stub_ask(monkeypatch, captured: dict | None = None):
    def _fake_post(url, json, timeout):
        if captured is not None:
            captured["url"] = url
            captured["json"] = json
        source = {"title": "Удар", "url": "https://pf2.ru/actions/strike", "source_book": ""}
        return _FakeAskResponse(200, {"answer": "Удар наносит урон.", "sources": [source]})

    monkeypatch.setattr(llm.httpx, "post", _fake_post)


def test_ask_requires_authentication(client) -> None:
    response = client.post("/llm/ask", json={"question": "Что делает Удар?"})

    assert response.status_code == 401


def test_ask_proxies_question_and_returns_answer(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    captured: dict = {}
    _stub_ask(monkeypatch, captured)

    response = client.post("/llm/ask", json={"question": "Что делает Удар?"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["answer"] == "Удар наносит урон."
    assert captured["url"].endswith("/ask")
    assert captured["json"] == {
        "question": "Что делает Удар?",
        "k": None,
        "character_context": None,
    }


def test_ask_sends_the_sheet_when_a_character_is_named(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    character_id = client.post(
        "/characters",
        json={"name": "Рэм Байер", "level": 5, "str_mod": 4},
        headers=headers,
    ).json()["id"]
    captured: dict = {}
    _stub_ask(monkeypatch, captured)

    response = client.post(
        "/llm/ask",
        json={"question": "Хватит ли мне Атлетики?", "character_id": character_id},
        headers=headers,
    )

    assert response.status_code == 200
    context = captured["json"]["character_context"]
    assert "Рэм Байер" in context
    assert "Атлетика (СИЛ): +4" in context
    # character_id is resolved here and must not leak onward to llm-service.
    assert "character_id" not in captured["json"]


def test_ask_refuses_a_character_owned_by_someone_else(client, monkeypatch) -> None:
    alice_headers = _auth_headers(client, email="alice@example.com")
    bob_headers = _auth_headers(client, email="bob@example.com")
    character_id = client.post(
        "/characters", json={"name": "Alice's PC"}, headers=alice_headers
    ).json()["id"]
    _stub_ask(monkeypatch)

    response = client.post(
        "/llm/ask",
        json={"question": "вопрос", "character_id": character_id},
        headers=bob_headers,
    )

    assert response.status_code == 404


def test_ask_returns_404_for_an_unknown_character(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    _stub_ask(monkeypatch)

    response = client.post(
        "/llm/ask", json={"question": "вопрос", "character_id": 999}, headers=headers
    )

    assert response.status_code == 404


def test_ask_forwards_llm_service_error_status(client, monkeypatch) -> None:
    headers = _auth_headers(client)

    def _fake_post(url, json, timeout):
        return _FakeAskResponse(503, {"detail": "not configured"})

    monkeypatch.setattr(llm.httpx, "post", _fake_post)

    response = client.post("/llm/ask", json={"question": "вопрос"}, headers=headers)

    assert response.status_code == 503


def test_ask_returns_502_when_llm_service_unreachable(client, monkeypatch) -> None:
    headers = _auth_headers(client)

    def _raise(url, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(llm.httpx, "post", _raise)

    response = client.post("/llm/ask", json={"question": "вопрос"}, headers=headers)

    assert response.status_code == 502
