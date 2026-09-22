from app.core.history import Turn
from app.core.prompts import build_ask_messages, build_system_prompt


def _flatten(messages: list[dict]) -> str:
    return "\n".join(message["content"] for message in messages)


def _system(messages: list[dict]) -> str:
    return messages[0]["content"]


def _question(messages: list[dict]) -> str:
    return messages[-1]["content"]


def test_build_ask_prompt_includes_context_and_question() -> None:
    retrieved = [
        {
            "id": "abc",
            "text": "Вы атакуете используемым оружием...",
            "metadata": {"title": "Удар", "source_book": "Основная книга игрока"},
            "distance": 0.1,
        }
    ]

    prompt = _question(build_ask_messages("Что делает действие Удар?", retrieved))

    assert "Удар" in prompt
    assert "Основная книга игрока" in prompt
    assert "Вы атакуете используемым оружием" in prompt
    assert "Что делает действие Удар?" in prompt


def test_build_ask_prompt_handles_no_context() -> None:
    prompt = _question(build_ask_messages("Вопрос без ответа", []))

    assert "контекст не найден" in prompt.lower()
    assert "Вопрос без ответа" in prompt


def test_weak_retrieval_adds_a_notice_before_the_context() -> None:
    """A second, code-checked reason to admit the gap — see retriever.is_weak."""
    retrieved = [
        {
            "id": "a",
            "text": "текст A",
            "metadata": {"title": "A", "source_book": "Книга"},
            "distance": 1.1,
        }
    ]

    prompt = _question(build_ask_messages("вопрос", retrieved, weak=True))

    assert "не подгоняй" in prompt.lower()
    assert "текст A" in prompt


def test_a_confident_retrieval_carries_no_weak_notice() -> None:
    retrieved = [{"id": "a", "text": "текст A", "metadata": {"title": "A"}, "distance": 0.1}]

    prompt = _question(build_ask_messages("вопрос", retrieved, weak=False))

    assert "не подгоняй" not in prompt.lower()


def test_weak_is_not_said_about_an_already_empty_context() -> None:
    """Empty context already reads as "контекст не найден" — a second,
    differently worded caveat on top of it would say the same thing twice."""
    prompt = _question(build_ask_messages("вопрос", [], weak=True))

    assert "не подгоняй" not in prompt.lower()
    assert "контекст не найден" in prompt.lower()


def test_build_ask_prompt_numbers_multiple_sources() -> None:
    retrieved = [
        {"id": "a", "text": "текст A", "metadata": {"title": "A", "source_book": "Книга"}},
        {"id": "b", "text": "текст B", "metadata": {"title": "B", "source_book": "Книга"}},
    ]

    prompt = _question(build_ask_messages("вопрос", retrieved))

    assert "[1] A" in prompt
    assert "[2] B" in prompt


def test_build_ask_prompt_omits_the_character_block_when_none_is_given() -> None:
    assert "Лист персонажа" not in _flatten(build_ask_messages("вопрос", []))


def test_build_ask_prompt_includes_the_character_sheet_when_given() -> None:
    system = _system(
        build_ask_messages("Хватит ли мне Атлетики?", [], "Персонаж: Рэм\nАтлетика: +12")
    )

    assert "Лист персонажа" in system
    assert "Атлетика: +12" in system


def test_character_block_tells_the_model_not_to_redo_the_arithmetic() -> None:
    assert "не пересчитывай" in _system(build_ask_messages("вопрос", [], "Персонаж: Рэм"))


def test_character_sheet_is_not_presented_as_a_source_of_rules() -> None:
    assert "не является источником правил" in _system(
        build_ask_messages("вопрос", [], "Персонаж: Рэм")
    )


def test_history_arrives_as_its_own_turns_not_glued_into_the_question() -> None:
    """Role tags are what let the model tell memory apart from the rules."""
    messages = build_ask_messages(
        "А если в броне?", [], history=[Turn("user", "Как работает Захват?")]
    )

    assert [message["role"] for message in messages] == ["system", "user", "user"]
    assert messages[1]["content"] == "Как работает Захват?"
    assert "Как работает Захват?" not in _question(messages)


def test_history_is_marked_as_memory_rather_than_a_source_of_rules() -> None:
    messages = build_ask_messages("вопрос", [], history=[Turn("user", "раньше")])

    assert "не являются источником правил" in _system(messages)


def test_nothing_is_said_about_history_when_there_is_none() -> None:
    assert "предыдущие сообщения" not in _system(build_ask_messages("вопрос", []))


def test_edit_instructions_discourage_asking_for_confirmation_in_prose() -> None:
    """Observed live: a build request got a "Согласовать?" reply in text
    instead of a propose_sheet_change call — the player already confirms
    every proposal in the UI, so that question is friction, not caution."""
    prompt = build_system_prompt("Персонаж: Рэм", allow_sheet_edits=True)

    assert "не спрашивай разрешения" in prompt
    assert "ask_clarifying_question" in prompt


def test_edit_instructions_are_absent_without_a_character() -> None:
    assert "propose_sheet_change" not in build_system_prompt(allow_sheet_edits=True)


def test_edit_instructions_require_a_complete_build() -> None:
    """Observed live: a "собери персонажа" request left feats unchosen and
    skill ranks untouched. Nothing told the model a build without them counts
    as done, so it stopped at whatever it happened to think of first."""
    prompt = build_system_prompt("Персонаж: Рэм", allow_sheet_edits=True)

    assert "rank" in prompt
    assert "черты" in prompt.lower()
    assert "слот" in prompt.lower()


def test_edit_instructions_tell_the_model_to_set_the_score_with_the_modifier() -> None:
    """The sheet shows a score next to every ability modifier and now flags a
    pair that disagrees — the model must be told the matching path exists and
    the arithmetic it has to honour, or every AI-built character shows a
    mismatch it had no way to avoid."""
    prompt = build_system_prompt("Персонаж: Рэм", allow_sheet_edits=True)

    assert "sheet_data.ability_scores" in prompt
    assert "10 + 2" in prompt


def test_retry_feedback_replaces_the_question_turn_verbatim() -> None:
    """This leg is web-backend reporting what its checker did with the
    model's last proposal — not a new question, so the usual "Контекст:
    ...\\nВопрос: ..." wrapping (which implies a search happened) is skipped
    entirely."""
    messages = build_ask_messages(
        "вопрос, который никогда не должен появиться",
        [{"id": "a", "text": "текст A", "metadata": {"title": "A", "source_book": "К"}}],
        retry_feedback="Отклонено: sheet_data.ancestry недоступен для правки",
    )

    last = messages[-1]
    assert last == {
        "role": "user",
        "content": "Отклонено: sheet_data.ancestry недоступен для правки",
    }
    assert "вопрос, который никогда не должен появиться" not in _flatten(messages)
    assert "текст A" not in _flatten(messages)


def test_retry_feedback_still_follows_the_remembered_turns() -> None:
    messages = build_ask_messages(
        "вопрос",
        [],
        history=[Turn("user", "Собери персонажа"), Turn("assistant", "Готово, вот план.")],
        retry_feedback="Отклонено: ...",
    )

    assert [message["role"] for message in messages] == ["system", "user", "assistant", "user"]
    assert messages[-1]["content"] == "Отклонено: ..."


def test_retry_feedback_keeps_the_character_and_edit_instructions() -> None:
    system = _system(
        build_ask_messages(
            "вопрос",
            [],
            character_context="Персонаж: Рэм",
            allow_sheet_edits=True,
            retry_feedback="Отклонено: ...",
        )
    )

    assert "Лист персонажа" in system
    assert "propose_sheet_change" in system


def test_the_rules_context_stays_next_to_the_question_it_was_found_for() -> None:
    retrieved = [{"id": "a", "text": "текст A", "metadata": {"title": "A", "source_book": "К"}}]

    messages = build_ask_messages("вопрос", retrieved, history=[Turn("user", "раньше")])

    assert "текст A" in _question(messages)
    assert "текст A" not in _system(messages)


def test_edit_instructions_ask_for_the_whole_stat_block_on_a_card() -> None:
    """Reported live: cards arrived with a name and nothing else — no
    description, prerequisites, action cost or requirements. Measured on the
    index built at the time, only 1.8% of feat chunks mentioned a
    prerequisite at all, so the corpus was fixed too; this is the half that
    tells the model those fields are its job."""
    prompt = build_system_prompt("Персонаж: Рэм", allow_sheet_edits=True)

    assert "стат-блок" in prompt
    assert "предварительные условия" in prompt
    assert "описание" in prompt


def test_edit_instructions_forbid_inventing_a_field_the_page_omits() -> None:
    """The dangerous failure is not an empty field, it is a plausible one: a
    made-up prerequisite reads exactly like a rule."""
    prompt = build_system_prompt("Персонаж: Рэм", allow_sheet_edits=True)

    assert "оставь пустым" in prompt
