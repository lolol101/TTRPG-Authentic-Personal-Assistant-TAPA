import httpx

from app.api import llm


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


def test_ask_proxies_question_and_returns_answer(client, monkeypatch) -> None:
    captured = {}

    def _fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        source = {"title": "Удар", "url": "https://pf2.ru/actions/strike", "source_book": ""}
        return _FakeAskResponse(200, {"answer": "Удар наносит урон.", "sources": [source]})

    monkeypatch.setattr(llm.httpx, "post", _fake_post)

    response = client.post("/llm/ask", json={"question": "Что делает Удар?"})

    assert response.status_code == 200
    assert response.json()["answer"] == "Удар наносит урон."
    assert captured["url"].endswith("/ask")
    assert captured["json"] == {"question": "Что делает Удар?", "k": None}


def test_ask_forwards_llm_service_error_status(client, monkeypatch) -> None:
    def _fake_post(url, json, timeout):
        return _FakeAskResponse(503, {"detail": "not configured"})

    monkeypatch.setattr(llm.httpx, "post", _fake_post)

    response = client.post("/llm/ask", json={"question": "вопрос"})

    assert response.status_code == 503


def test_ask_returns_502_when_llm_service_unreachable(client, monkeypatch) -> None:
    def _raise(url, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(llm.httpx, "post", _raise)

    response = client.post("/llm/ask", json={"question": "вопрос"})

    assert response.status_code == 502
