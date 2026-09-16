"""Asks the question a second time in the language the rules are written in.

The corpus is English — the Foundry PF2e packs. bge-m3 retrieves across
languages, but not equally well: measured on this index, the page that
answers an English question sits at ranks 1-13, and the page that answers
the same question in Russian sits at ranks 20-50 or lower. Raising `k` far
enough to reach that is a worse trade than asking once more in English,
because everything between rank 5 and rank 30 is context spent on noise.

So: one cheap call that names the rule in the book's own words —
"Что делает действие Устрашение?" becomes "Demoralize action" — and the
search runs twice, once per phrasing. Rewriting is a rewrite, not a
translation: what retrieves well is the term the book uses, not a faithful
rendering of the player's sentence.

The rewrite is strictly optional. A model that declines, fails or answers
with nonsense leaves the request on exactly the retrieval it had before.
"""

from __future__ import annotations

import logging

from app.core.llm_provider import Completion, complete
from app.core.tools import REWRITE_SEARCH_QUERY, SEARCH_QUERY_TOOL, parse_search_query

_log = logging.getLogger(__name__)

_REWRITE_INSTRUCTIONS = (
    "Ты готовишь поисковый запрос по книгам правил Pathfinder 2e. Книги на "
    "английском. Тебе дан вопрос игрока. Если он не на английском или "
    "сформулирован разговорно — вызови инструмент и дай короткий английский "
    "запрос из терминов правил: как эта вещь называется в книге. Не отвечай "
    "на сам вопрос и не переводи его дословно. Если вопрос уже короткий и "
    "английский — не вызывай инструмент вообще."
)


def _ask_for_rewrite(question: str) -> Completion:
    return complete(
        [
            {"role": "system", "content": _REWRITE_INSTRUCTIONS},
            {"role": "user", "content": question},
        ],
        tools=[SEARCH_QUERY_TOOL],
    )


def rewrite_for_search(question: str) -> str | None:
    """The same question in the rulebooks' language, or None to search as-is.

    Never raises: this runs before every ordinary question, and a rewrite
    that fails must cost the answer nothing.
    """
    try:
        completion = _ask_for_rewrite(question)
    except Exception as exc:  # noqa: BLE001 — rewriting is strictly optional
        _log.warning(
            "query rewriting unavailable (%s); searching the question as asked",
            type(exc).__name__,
        )
        return None

    raw = completion.tool_arguments.get(REWRITE_SEARCH_QUERY)
    if not raw:
        return None

    rewritten = parse_search_query(raw)
    # Searching the same string twice costs an embedding and returns the
    # same hits, so a rewrite that changed nothing is no rewrite.
    if not rewritten or rewritten.casefold() == question.strip().casefold():
        return None

    _log.info("search rewritten: %r -> %r", question, rewritten)
    return rewritten


__all__ = ["rewrite_for_search"]
