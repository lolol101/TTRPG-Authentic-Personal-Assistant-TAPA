from app.core.tools import CLARIFY_TOOL, parse_clarification


def test_reads_a_question_with_its_options() -> None:
    raw = '{"question": "От какого значения считать?", "options": ["40", "28"]}'

    assert parse_clarification(raw) == {
        "question": "От какого значения считать?",
        "options": ["40", "28"],
    }


def test_options_are_optional() -> None:
    assert parse_clarification('{"question": "Сколько урона?"}') == {
        "question": "Сколько урона?",
        "options": [],
    }


def test_a_call_without_a_question_says_nothing() -> None:
    """Better no clarification than an empty bubble asking the player nothing."""
    assert parse_clarification('{"options": ["да", "нет"]}') is None
    assert parse_clarification('{"question": "   "}') is None


def test_malformed_arguments_do_not_raise() -> None:
    assert parse_clarification("не json") is None
    assert parse_clarification("[1, 2]") is None


def test_a_wall_of_options_is_trimmed() -> None:
    """Twenty buttons is not a question, it is a form."""
    raw = '{"question": "Что?", "options": ["1","2","3","4","5","6","7"]}'

    assert len(parse_clarification(raw)["options"]) == 5


def test_the_tool_tells_the_model_when_not_to_ask() -> None:
    description = CLARIFY_TOOL["function"]["description"]

    assert "Если всё ясно" in description


def test_the_clarify_tool_is_offered_only_with_a_sheet_in_play() -> None:
    """A rules answer the model half-understood is cheap to correct; a sheet
    edited on a guess is not — so asking is offered only where it matters."""
    from app.api.ask import _tools_for
    from app.core.tools import ASK_CLARIFICATION
    from app.schemas.ask import AskRequest

    with_sheet = _tools_for(
        AskRequest(question="q", character_context="Персонаж: Рэм", allow_sheet_edits=True)
    )
    without = _tools_for(AskRequest(question="q"))

    assert ASK_CLARIFICATION in [tool["function"]["name"] for tool in with_sheet]
    assert without is None


def test_a_clarification_reaches_the_caller(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.api import ask
    from app.core.llm_provider import Completion
    from app.main import app

    monkeypatch.setattr(ask, "retrieve", lambda question, k, ruleset=None: [])
    monkeypatch.setattr(
        ask,
        "complete",
        lambda messages, tools=None: Completion(
            "", clarification={"question": "Сколько урона?", "options": ["5", "10"]}
        ),
    )

    body = TestClient(app).post("/ask", json={"question": "мне попали"}).json()

    assert body["clarification"] == {"question": "Сколько урона?", "options": ["5", "10"]}


def test_no_clarification_means_null_not_an_empty_question(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.api import ask
    from app.core.llm_provider import Completion
    from app.main import app

    monkeypatch.setattr(ask, "retrieve", lambda question, k, ruleset=None: [])
    monkeypatch.setattr(ask, "complete", lambda messages, tools=None: Completion("ответ"))

    body = TestClient(app).post("/ask", json={"question": "вопрос"}).json()

    assert body["clarification"] is None
