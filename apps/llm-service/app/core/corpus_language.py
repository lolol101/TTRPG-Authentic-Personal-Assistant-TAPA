"""What the prompts say about the language the rulebooks are indexed in.

Two corpora are built from the same packs (docs/rfc/0001): the English
original and the same records with the Russian translation laid over them.
The prompts used to state "the books are English" as a fact; it is now a
property of the index being served, set by `corpus_language`, and every
sentence that depends on it lives here so the two cannot drift apart.

The English wording is the one the golden set was measured against — keep it
verbatim when editing the Russian one.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class CorpusWording:
    #: Where the answer's pages come from, as the answering prompt states it.
    source: str
    #: How the rewrite is told what language the books are in.
    books: str
    #: The tool the rewrite answers through; the name itself steers the model.
    rewrite_tool: str
    rewrite_tool_purpose: str
    #: What a search query is, said to the rewrite and the sheet planner.
    queries: str
    queries_detail: str
    plan_query_hint: str
    plan_area_query_hint: str
    #: How a digest quotes the pages.
    digest_quote: str


_ENGLISH = CorpusWording(
    source="только открытый ORC-контент из официальных паков foundryvtt/pf2e, на английском",
    books="Книги на английском.",
    rewrite_tool="search_the_rulebooks_in_english",
    rewrite_tool_purpose="дать английские поисковые запросы по книге правил",
    queries="дай короткие английские запросы из терминов правил",
    queries_detail=(
        "Для standalone_question: по одному короткому "
        "английскому запросу на каждое правило, о "
        "котором спрашивают. Запрос — это термин из книги: "
        "название действия, черты, заклинания, снаряжения, "
        "состояния. Не переводи дословно и не пиши "
        "предложение — пиши то, как это называется в книге. "
        "«Что делает действие Устрашение?» → "
        "[«Demoralize action»]. Если в вопросе несколько "
        "правил сразу, назови каждое отдельным запросом: "
        "«Могу ли я схватить противника, если сам напуган?» → "
        "[«Grapple action», «Frightened condition»]. Не дроби "
        "одно правило на несколько запросов и не добавляй "
        "правила, о которых не спрашивали."
    ),
    plan_query_hint="(лучше по-английски: книги правил на английском)",
    plan_area_query_hint="Лучше по-английски — книги правил на английском.",
    digest_quote="по-английски и словами книги",
)

_RUSSIAN = CorpusWording(
    source=(
        "открытый ORC/OGL-контент из официальных паков foundryvtt/pf2e в русском "
        "переводе сообщества; где перевода нет — на английском"
    ),
    books=(
        "Книги на русском, у каждой страницы в заголовке стоит и английское "
        "название, например «Захватить (Grapple)»."
    ),
    rewrite_tool="search_the_rulebooks",
    rewrite_tool_purpose="дать поисковые запросы по книге правил",
    queries="дай короткие запросы из терминов правил",
    queries_detail=(
        "Для standalone_question: по одному короткому "
        "запросу на каждое правило, о котором спрашивают. "
        "Запрос — это термин из книги: название действия, "
        "черты, заклинания, снаряжения, состояния, как оно "
        "названо в русском переводе. Не пиши предложение — "
        "пиши то, как это называется в книге. "
        "«Что делает действие Устрашение?» → "
        "[«Деморализовать»]. Если в вопросе несколько "
        "правил сразу, назови каждое отдельным запросом: "
        "«Могу ли я схватить противника, если сам напуган?» → "
        "[«Захватить», «Напуган»]. Не дроби одно правило на "
        "несколько запросов и не добавляй правила, о которых "
        "не спрашивали."
    ),
    plan_query_hint="(терминами книги правил)",
    plan_area_query_hint="Терминами книги правил.",
    digest_quote="словами книги",
)

_WORDINGS = {"en": _ENGLISH, "ru": _RUSSIAN}


def wording() -> CorpusWording:
    return _WORDINGS[settings.corpus_language]
