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
    monkeypatch.setattr(ask, "retrieve", lambda question, k, ruleset=None: _FAKE_RETRIEVED)
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
    monkeypatch.setattr(ask, "retrieve", lambda question, k, ruleset=None: [])

    def _raise(prompt, tools=None):
        raise LLMNotConfiguredError("LLM_API_KEY is not set")

    monkeypatch.setattr(ask, "complete", _raise)

    response = client.post("/ask", json={"question": "вопрос"})

    assert response.status_code == 503


def test_ask_returns_502_on_provider_error(monkeypatch) -> None:
    monkeypatch.setattr(ask, "retrieve", lambda question, k, ruleset=None: [])

    def _raise(prompt, tools=None):
        raise OpenAIError("boom")

    monkeypatch.setattr(ask, "complete", _raise)

    response = client.post("/ask", json={"question": "вопрос"})

    assert response.status_code == 502


def test_ask_passes_k_through_to_retrieve(monkeypatch) -> None:
    captured = {}

    def _fake_retrieve(question, k, ruleset=None):
        captured["question"] = question
        captured["k"] = k
        return []

    monkeypatch.setattr(ask, "retrieve", _fake_retrieve)
    monkeypatch.setattr(ask, "complete", lambda prompt, tools=None: Completion("ok"))

    client.post("/ask", json={"question": "вопрос про Удар", "k": 3})

    assert captured == {"question": "вопрос про Удар", "k": 3}


def test_history_reaches_the_model_as_earlier_turns(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(ask, "retrieve", lambda question, k, ruleset=None: [])

    def _fake_complete(messages, tools=None):
        captured["messages"] = messages
        return Completion("ok")

    monkeypatch.setattr(ask, "complete", _fake_complete)

    client.post(
        "/ask",
        json={
            "question": "А если в броне?",
            "history": [
                {"role": "user", "text": "Как работает Захват?"},
                {"role": "assistant", "text": "Захват обездвиживает цель."},
            ],
        },
    )

    roles = [message["role"] for message in captured["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert captured["messages"][2]["content"] == "Захват обездвиживает цель."


def test_a_follow_up_is_searched_with_the_question_it_follows(monkeypatch) -> None:
    captured = {}

    def _fake_retrieve(question, k, ruleset=None):
        captured["question"] = question
        return []

    monkeypatch.setattr(ask, "retrieve", _fake_retrieve)
    monkeypatch.setattr(ask, "complete", lambda messages, tools=None: Completion("ok"))

    client.post(
        "/ask",
        json={
            "question": "А если в броне?",
            "history": [{"role": "user", "text": "Как работает Захват?"}],
        },
    )

    assert "Захват" in captured["question"]


def test_the_answer_reports_how_much_of_the_chat_was_remembered(monkeypatch) -> None:
    monkeypatch.setattr(ask, "retrieve", lambda question, k, ruleset=None: [])
    monkeypatch.setattr(ask, "complete", lambda messages, tools=None: Completion("ok"))

    response = client.post(
        "/ask",
        json={
            "question": "вопрос",
            "history": [{"role": "user", "text": "раньше"}],
        },
    )

    memory = response.json()["memory"]
    assert memory["used"] == 1
    assert memory["dropped"] == 0
    assert memory["budget"] > 0


def test_turns_that_do_not_fit_the_budget_are_reported_as_dropped(monkeypatch) -> None:
    """The reader is told where memory ends rather than left to guess."""
    monkeypatch.setattr(ask, "retrieve", lambda question, k, ruleset=None: [])
    monkeypatch.setattr(ask, "complete", lambda messages, tools=None: Completion("ok"))
    monkeypatch.setattr(ask.settings, "history_token_budget", 30)

    response = client.post(
        "/ask",
        json={
            "question": "вопрос",
            "history": [
                {"role": "user", "text": "очень длинный вопрос " * 50},
                {"role": "assistant", "text": "очень длинный ответ " * 50},
                {"role": "user", "text": "короткий"},
            ],
        },
    )

    memory = response.json()["memory"]
    assert memory["used"] == 1
    assert memory["dropped"] == 2
