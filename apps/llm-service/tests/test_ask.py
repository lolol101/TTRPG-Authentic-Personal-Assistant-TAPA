from fastapi.testclient import TestClient
from openai import OpenAIError

from app.api import ask
from app.core.llm_provider import Completion, LLMNotConfiguredError
from app.main import app

client = TestClient(app)

_FAKE_RETRIEVED = [
    {
        "id": "abc",
        "text": "Вы атакуете используемым оружием...",
        "metadata": {
            "title": "Удар",
            "url": "https://pf2.ru/actions/strike",
            "source_book": "Основная книга игрока",
        },
        "distance": 0.1,
    }
]


def test_ask_returns_answer_and_sources(monkeypatch) -> None:
    monkeypatch.setattr(ask, "retrieve", lambda question, k: _FAKE_RETRIEVED)
    monkeypatch.setattr(
        ask, "complete", lambda prompt, tools=None: Completion("Удар наносит урон.")
    )

    response = client.post("/ask", json={"question": "Что делает Удар?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Удар наносит урон."
    assert body["sources"] == [
        {
            "title": "Удар",
            "url": "https://pf2.ru/actions/strike",
            "source_book": "Основная книга игрока",
        }
    ]


def test_ask_returns_503_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(ask, "retrieve", lambda question, k: [])

    def _raise(prompt, tools=None):
        raise LLMNotConfiguredError("LLM_API_KEY is not set")

    monkeypatch.setattr(ask, "complete", _raise)

    response = client.post("/ask", json={"question": "вопрос"})

    assert response.status_code == 503


def test_ask_returns_502_on_provider_error(monkeypatch) -> None:
    monkeypatch.setattr(ask, "retrieve", lambda question, k: [])

    def _raise(prompt, tools=None):
        raise OpenAIError("boom")

    monkeypatch.setattr(ask, "complete", _raise)

    response = client.post("/ask", json={"question": "вопрос"})

    assert response.status_code == 502


def test_ask_passes_k_through_to_retrieve(monkeypatch) -> None:
    captured = {}

    def _fake_retrieve(question, k):
        captured["question"] = question
        captured["k"] = k
        return []

    monkeypatch.setattr(ask, "retrieve", _fake_retrieve)
    monkeypatch.setattr(ask, "complete", lambda prompt, tools=None: Completion("ok"))

    client.post("/ask", json={"question": "вопрос про Удар", "k": 3})

    assert captured == {"question": "вопрос про Удар", "k": 3}
