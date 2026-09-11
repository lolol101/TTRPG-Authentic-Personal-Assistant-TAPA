from app.core.history import Turn, estimate_tokens, fit_history, retrieval_query


def _turns(*pairs: tuple[str, str]) -> list[Turn]:
    return [Turn(role=role, text=text) for role, text in pairs]


def test_estimate_grows_with_the_text() -> None:
    assert estimate_tokens("") < estimate_tokens("короткий") < estimate_tokens("короткий" * 20)


def test_estimate_does_not_undercount_cyrillic() -> None:
    """Russian costs roughly two to three characters per token, not four.

    Estimating like English would let a full window through as "fits".
    """
    assert estimate_tokens("я" * 100) >= 40


def test_everything_fits_when_the_budget_is_generous() -> None:
    history = _turns(("user", "вопрос"), ("assistant", "ответ"))

    fitted = fit_history(history, budget=1000)

    assert fitted.messages == history
    assert fitted.dropped == 0


def test_the_oldest_turns_are_the_ones_dropped() -> None:
    history = _turns(
        ("user", "первый" * 50),
        ("assistant", "ответ" * 50),
        ("user", "последний"),
    )

    fitted = fit_history(history, budget=60)

    assert fitted.messages[-1].text == "последний"
    assert fitted.dropped > 0
    assert len(fitted.messages) < len(history)


def test_an_answer_is_never_kept_without_its_question() -> None:
    """An assistant turn on its own reads as something the player said next."""
    history = _turns(("user", "длинный вопрос" * 40), ("assistant", "короткий ответ"))

    fitted = fit_history(history, budget=20)

    assert [turn.role for turn in fitted.messages] != ["assistant"]


def test_nothing_is_kept_when_even_one_turn_is_too_large() -> None:
    fitted = fit_history(_turns(("user", "я" * 5000)), budget=10)

    assert fitted.messages == []
    assert fitted.dropped == 1


def test_an_empty_history_is_not_an_error() -> None:
    fitted = fit_history([], budget=100)

    assert fitted.messages == []
    assert fitted.dropped == 0
    assert fitted.tokens == 0


def test_tokens_report_what_was_kept_not_what_was_offered() -> None:
    history = _turns(("user", "а" * 300), ("user", "б" * 30))

    fitted = fit_history(history, budget=40)

    assert fitted.tokens <= 40
    assert fitted.tokens > 0


def test_a_follow_up_is_searched_together_with_what_it_follows() -> None:
    """ "А если он в тяжёлой броне?" matches no rule page on its own."""
    history = _turns(("user", "Как работает Захват?"), ("assistant", "Захват — это..."))

    query = retrieval_query("А если он в тяжёлой броне?", history)

    assert "Захват" in query
    assert "тяжёлой броне" in query


def test_the_search_query_ignores_what_the_assistant_said() -> None:
    """Its own prose would swamp the player's words in the embedding."""
    history = _turns(("user", "Как работает Захват?"), ("assistant", "Захват" * 200))

    query = retrieval_query("А если в броне?", history)

    assert "Захват" * 200 not in query


def test_the_first_question_is_searched_as_written() -> None:
    assert retrieval_query("Что делает Удар?", []) == "Что делает Удар?"
