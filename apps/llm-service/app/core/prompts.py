from typing import Any

from app.core.history import Turn

ASK_SYSTEM_INSTRUCTIONS = (
    "Ты — помощник по правилам Pathfinder 2e (только открытый ORC-контент, "
    "переводы pf2.ru). Отвечай ТОЛЬКО на основе приведённого ниже контекста. "
    "Если в контексте нет ответа на вопрос — прямо скажи об этом, не выдумывай "
    "правила. Отвечай на русском, кратко и по делу."
)

CHARACTER_INSTRUCTIONS = (
    "Ниже дан лист персонажа игрока. Модификаторы в нём уже посчитаны — бери "
    "их как есть и не пересчитывай. Если вопрос касается этого персонажа, "
    "опирайся на его числа. Лист персонажа не является источником правил: "
    "сами правила бери только из контекста ниже."
)


HISTORY_INSTRUCTIONS = (
    "Перед последним вопросом идут предыдущие сообщения этого чата. Они нужны "
    "только чтобы понимать, о чём спрашивает игрок: твои прошлые ответы не "
    "являются источником правил. Правила бери из контекста при последнем вопросе."
)


EDIT_INSTRUCTIONS = (
    "Если игрок просит изменить лист (получил урон, наложено состояние, "
    "потрачен пункт героизма, повысилось умение) — вызови инструмент "
    "propose_sheet_change. Изменения не применяются сразу: игрок подтверждает "
    "их вручную, поэтому предлагай только то, о чём тебя действительно "
    "попросили, и передавай новое значение целиком, а не разницу."
)


def _context_block(retrieved: list[dict[str, Any]]) -> str:
    if not retrieved:
        return "(контекст не найден)"
    return "\n\n".join(
        f"[{i + 1}] {r['metadata']['title']} "
        f"(источник: {r['metadata'].get('source_book') or 'неизвестен'}):\n{r['text']}"
        for i, r in enumerate(retrieved)
    )


def build_system_prompt(
    character_context: str | None = None,
    allow_sheet_edits: bool = False,
    with_history: bool = False,
) -> str:
    parts = [ASK_SYSTEM_INSTRUCTIONS]
    if character_context:
        parts.append(f"{CHARACTER_INSTRUCTIONS}\n\nЛист персонажа:\n{character_context}")
        if allow_sheet_edits:
            parts.append(EDIT_INSTRUCTIONS)
    if with_history:
        parts.append(HISTORY_INSTRUCTIONS)
    return "\n\n".join(parts)


def build_ask_messages(
    question: str,
    retrieved: list[dict[str, Any]],
    character_context: str | None = None,
    allow_sheet_edits: bool = False,
    history: list[Turn] | None = None,
) -> list[dict[str, Any]]:
    """Instructions, then the remembered turns, then this question.

    The retrieved rules travel with the question rather than sitting in the
    system message: they were retrieved for *this* question, and putting them
    above the dialogue invites the model to answer an earlier one with them.
    """
    history = history or []

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": build_system_prompt(
                character_context, allow_sheet_edits, with_history=bool(history)
            ),
        }
    ]
    messages.extend({"role": turn.role, "content": turn.text} for turn in history)
    messages.append(
        {
            "role": "user",
            "content": f"Контекст:\n{_context_block(retrieved)}\n\nВопрос: {question}",
        }
    )
    return messages
