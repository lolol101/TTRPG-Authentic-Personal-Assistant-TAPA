from typing import Any

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


EDIT_INSTRUCTIONS = (
    "Если игрок просит изменить лист (получил урон, наложено состояние, "
    "потрачен пункт героизма, повысилось умение) — вызови инструмент "
    "propose_sheet_change. Изменения не применяются сразу: игрок подтверждает "
    "их вручную, поэтому предлагай только то, о чём тебя действительно "
    "попросили, и передавай новое значение целиком, а не разницу."
)


def build_ask_prompt(
    question: str,
    retrieved: list[dict[str, Any]],
    character_context: str | None = None,
    allow_sheet_edits: bool = False,
) -> str:
    if not retrieved:
        context_block = "(контекст не найден)"
    else:
        context_block = "\n\n".join(
            f"[{i + 1}] {r['metadata']['title']} "
            f"(источник: {r['metadata'].get('source_book') or 'неизвестен'}):\n{r['text']}"
            for i, r in enumerate(retrieved)
        )

    character_block = ""
    if character_context:
        character_block = f"{CHARACTER_INSTRUCTIONS}\n\nЛист персонажа:\n{character_context}\n\n"
        if allow_sheet_edits:
            character_block += f"{EDIT_INSTRUCTIONS}\n\n"

    return (
        f"{ASK_SYSTEM_INSTRUCTIONS}\n\n"
        f"{character_block}"
        f"Контекст:\n{context_block}\n\n"
        f"Вопрос: {question}"
    )
