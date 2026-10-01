"""Names the question in the language the rules are written in, once per rule.

The corpus is English — the Foundry PF2e packs. bge-m3 retrieves across
languages, but not equally well: measured on this index, the page that
answers an English question sits at ranks 1-13, and the page that answers
the same question in Russian sits at ranks 20-50 or lower. Raising `k` far
enough to reach that is a worse trade than asking once more in English,
because everything between rank 5 and rank 30 is context spent on noise.

So: one cheap call that names the rule in the book's own words —
"Что делает действие Устрашение?" becomes "Demoralize action" — and the
search runs once per name it gives, plus once on the question as asked.
Rewriting is a rewrite, not a translation: what retrieves well is the term
the book uses, not a faithful rendering of the player's sentence.

A question often names more than one rule, and asking for a single query
loses all but one of them. Measured over six two-rule questions on the live
index, scoring whether each rule's own page was retrieved at all:

    one query for the whole question    8/12 concepts
    one query per named concept        11/12 concepts

The four misses were not pages ranked too deep — they were concepts the
rewrite never mentioned, so nothing ever searched for them: "Могу ли я
схватить противника (Grapple), если сам напуган (Frightened)?" came back
as "Grapple action" and Frightened was simply gone. Hence a list. The extra
queries cost an embedding and a search each, not another completion: the one
call this module already makes on every question now answers with all of
them at once.

The same call also restates the question so it reads without the dialogue.
Searching a follow-up used to mean gluing the previous question in front of
it — right for "А если он в тяжёлой броне?", wrong the moment the topic
changes: replayed live, "Что я могу купить на своём уровне?" after a talk
about slowing spells was searched as both, found Slow and Stagnate Time, and
was answered 3 times of 3 as a question about buying spells. The model that
already reads the question decides which it is, at no extra call.

The rewrite is strictly optional. A model that declines, fails or answers
with nonsense leaves the request on exactly the retrieval it had before.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.history import Turn
from app.core.llm_provider import Completion, complete
from app.core.tools import (
    REWRITE_SEARCH_QUERY,
    SEARCH_QUERY_TOOL,
    parse_search_queries,
    parse_standalone_question,
)

_log = logging.getLogger(__name__)

_REWRITE_INSTRUCTIONS = (
    "Ты готовишь новый вопрос игрока к поиску по книгам правил Pathfinder 2e. "
    "Книги на английском. Тебе даны последние сообщения чата и новый вопрос. "
    "Всегда вызывай инструмент. В standalone_question перепиши новый вопрос "
    "по-русски так, чтобы он был понятен без переписки: если он ссылается на "
    "прошлое — подставь, о ком и о чём речь; если он о новом — не добавляй "
    "прошлую тему. В queries дай короткие английские запросы из терминов "
    "правил: как эта вещь называется в книге. Если в вопросе названо "
    "несколько правил (действие и состояние, заклинание и состояние), дай "
    "отдельный запрос на каждое: по одному запросу найдётся только первое, а "
    "про остальные ответ будет выдуман. Не отвечай на сам вопрос и не "
    "переводи его дословно."
)


@dataclass(frozen=True)
class Rewrite:
    """The question prepared for search.

    standalone is None when the model gave nothing usable: the caller then
    falls back to the old glued search rather than guessing.
    """

    standalone: str | None = None
    queries: list[str] = field(default_factory=list)


def _dialogue(history: list[Turn]) -> str:
    recent = history[-settings.rewrite_history_messages :] if history else []
    lines = []
    for turn in recent:
        if turn.role == "user":
            lines.append(f"Игрок: {turn.text}")
        else:
            lines.append(f"Ассистент: {turn.text[: settings.rewrite_history_answer_chars]}")
    return "\n".join(lines)


def _ask_for_rewrite(question: str, history: list[Turn]) -> Completion:
    dialogue = _dialogue(history)
    content = (
        f"Последние сообщения:\n{dialogue}\n\nНовый вопрос: {question}"
        if dialogue
        else f"Новый вопрос: {question}"
    )
    return complete(
        [
            {"role": "system", "content": _REWRITE_INSTRUCTIONS},
            {"role": "user", "content": content},
        ],
        tools=[SEARCH_QUERY_TOOL],
    )


def rewrite_question(question: str, history: list[Turn]) -> Rewrite:
    """The question restated without the dialogue, and the rules it names.

    Never raises: this runs before every ordinary question, and a rewrite
    that fails must cost the answer nothing.
    """
    try:
        completion = _ask_for_rewrite(question, history)
    except Exception as exc:  # noqa: BLE001 — rewriting is strictly optional
        _log.warning(
            "query rewriting unavailable (%s); searching the question as asked",
            type(exc).__name__,
        )
        return Rewrite()

    raw = completion.tool_arguments.get(REWRITE_SEARCH_QUERY)
    if not raw:
        return Rewrite()

    standalone = parse_standalone_question(raw)
    # Searching the same string twice costs an embedding and returns the
    # same hits, so a query that restates the question is no rewrite.
    already = {question.strip().casefold(), (standalone or "").casefold()}
    queries = [query for query in parse_search_queries(raw) if query.casefold() not in already]
    queries = queries[: settings.retrieval_max_search_queries]

    _log.info("question rewritten: %r -> %r %s", question, standalone, queries)
    return Rewrite(standalone=standalone, queries=queries)


__all__ = ["Rewrite", "rewrite_question"]
