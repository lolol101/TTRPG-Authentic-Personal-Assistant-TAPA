from fastapi.testclient import TestClient
from openai import OpenAIError

from app.api import chat
from app.core.llm_provider import LLMNotConfiguredError
from app.main import app

client = TestClient(app)


def test_chat_returns_reply(monkeypatch) -> None:
    monkeypatch.setattr(chat, "get_completion", lambda message: f"echo: {message}")

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"reply": "echo: hello"}


def test_chat_returns_503_when_not_configured(monkeypatch) -> None:
    def _raise(message: str) -> str:
        raise LLMNotConfiguredError("LLM_API_KEY is not set")

    monkeypatch.setattr(chat, "get_completion", _raise)

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 503


def test_chat_returns_502_on_provider_error(monkeypatch) -> None:
    def _raise(message: str) -> str:
        raise OpenAIError("connection failed")

    monkeypatch.setattr(chat, "get_completion", _raise)

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 502
