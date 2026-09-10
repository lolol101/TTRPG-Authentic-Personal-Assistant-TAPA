import httpx
import openai
from fastapi.testclient import TestClient

from app.api import chat
from app.main import app

client = TestClient(app)


def test_chat_returns_provider_reply(monkeypatch) -> None:
    monkeypatch.setattr(chat.llm_provider, "complete", lambda message: f"echo: {message}")

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"reply": "echo: hello"}


def test_chat_returns_502_when_provider_unreachable(monkeypatch) -> None:
    def _raise(message: str) -> str:
        request = httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
        raise openai.APIConnectionError(request=request)

    monkeypatch.setattr(chat.llm_provider, "complete", _raise)

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 502
