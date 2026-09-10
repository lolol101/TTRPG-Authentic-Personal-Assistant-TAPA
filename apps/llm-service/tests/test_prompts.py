from app.core.prompts import build_ask_prompt


def test_build_ask_prompt_includes_context_and_question() -> None:
    retrieved = [
        {
            "id": "abc",
            "text": "Вы атакуете используемым оружием...",
            "metadata": {"title": "Удар", "source_book": "Основная книга игрока"},
            "distance": 0.1,
        }
    ]

    prompt = build_ask_prompt("Что делает действие Удар?", retrieved)

    assert "Удар" in prompt
    assert "Основная книга игрока" in prompt
    assert "Вы атакуете используемым оружием" in prompt
    assert "Что делает действие Удар?" in prompt


def test_build_ask_prompt_handles_no_context() -> None:
    prompt = build_ask_prompt("Вопрос без ответа", [])

    assert "контекст не найден" in prompt.lower()
    assert "Вопрос без ответа" in prompt


def test_build_ask_prompt_numbers_multiple_sources() -> None:
    retrieved = [
        {"id": "a", "text": "текст A", "metadata": {"title": "A", "source_book": "Книга"}},
        {"id": "b", "text": "текст B", "metadata": {"title": "B", "source_book": "Книга"}},
    ]

    prompt = build_ask_prompt("вопрос", retrieved)

    assert "[1] A" in prompt
    assert "[2] B" in prompt


def test_build_ask_prompt_omits_the_character_block_when_none_is_given() -> None:
    prompt = build_ask_prompt("вопрос", [])

    assert "Лист персонажа" not in prompt


def test_build_ask_prompt_includes_the_character_sheet_when_given() -> None:
    prompt = build_ask_prompt("Хватит ли мне Атлетики?", [], "Персонаж: Рэм\nАтлетика: +12")

    assert "Лист персонажа" in prompt
    assert "Атлетика: +12" in prompt


def test_character_block_tells_the_model_not_to_redo_the_arithmetic() -> None:
    prompt = build_ask_prompt("вопрос", [], "Персонаж: Рэм")

    assert "не пересчитывай" in prompt


def test_character_sheet_is_not_presented_as_a_source_of_rules() -> None:
    prompt = build_ask_prompt("вопрос", [], "Персонаж: Рэм")

    assert "не является источником правил" in prompt
