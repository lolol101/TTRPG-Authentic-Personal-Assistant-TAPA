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

The rewrite is strictly optional. A model that declines, fails or answers
with nonsense leaves the request on exactly the retrieval it had before.
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.llm_provider import Completion, complete
from app.core.tools import REWRITE_SEARCH_QUERY, SEARCH_QUERY_TOOL, parse_search_queries

_log = logging.getLogger(__name__)

_REWRITE_INSTRUCTIONS = (
    "Ты готовишь поисковые запросы по книгам правил Pathfinder 2e. Книги на "
    "английском. Тебе дан вопрос игрока. Если он не на английском или "
    "сформулирован разговорно — вызови инструмент и дай короткие английские "
    "запросы из терминов правил: как эта вещь называется в книге. Если в "
    "вопросе названо несколько правил (действие и состояние, заклинание и "
    "состояние), дай отдельный запрос на каждое: по одному запросу найдётся "
    "только первое, а про остальные ответ будет выдуман. Не отвечай на сам "
    "вопрос и не переводи его дословно. Если вопрос уже короткий и "
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


def search_queries_for(question: str) -> list[str]:
    """The rules named in the rulebooks' language, one query each.

    Empty means search the question as it was asked and nothing else. Never
    raises: this runs before every ordinary question, and a rewrite that
    fails must cost the answer nothing.
    """
    try:
        completion = _ask_for_rewrite(question)
    except Exception as exc:  # noqa: BLE001 — rewriting is strictly optional
        _log.warning(
            "query rewriting unavailable (%s); searching the question as asked",
            type(exc).__name__,
        )
        return []

    raw = completion.tool_arguments.get(REWRITE_SEARCH_QUERY)
    if not raw:
        return []

    asked = question.strip().casefold()
    # Searching the same string twice costs an embedding and returns the
    # same hits, so a query that restates the question is no rewrite.
    queries = [query for query in parse_search_queries(raw) if query.casefold() != asked]
    queries = queries[: settings.retrieval_max_search_queries]

    if queries:
        _log.info("search rewritten: %r -> %s", question, queries)
    return queries


__all__ = ["search_queries_for"]
