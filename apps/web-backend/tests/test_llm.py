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
