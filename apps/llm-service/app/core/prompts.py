from typing import Any

ASK_SYSTEM_INSTRUCTIONS = (
    "Ты — помощник по правилам Pathfinder 2e (только открытый ORC-контент, "
    "переводы pf2.ru). Отвечай ТОЛЬКО на основе приведённого ниже контекста. "
    "Если в контексте нет ответа на вопрос — прямо скажи об этом, не выдумывай "
    "правила. Отвечай на русском, кратко и по делу."
)


def build_ask_prompt(question: str, retrieved: list[dict[str, Any]]) -> str:
    if not retrieved:
        context_block = "(контекст не найден)"
    else:
        context_block = "\n\n".join(
            f"[{i + 1}] {r['metadata']['title']} "
            f"(источник: {r['metadata'].get('source_book') or 'неизвестен'}):\n{r['text']}"
            for i, r in enumerate(retrieved)
        )

    return (
        f"{ASK_SYSTEM_INSTRUCTIONS}\n\n"
        f"Контекст:\n{context_block}\n\n"
        f"Вопрос: {question}"
    )
