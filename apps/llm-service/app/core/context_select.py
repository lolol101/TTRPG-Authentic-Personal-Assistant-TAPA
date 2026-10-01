"""Narrows what retrieval found to what actually answers the question.

Retrieval ranks by embedding distance, and a page can sit close to a question
by sharing its words without saying anything about it. Two steps stand
between the search and the answer:

1. within_distance — a coarse cut against outright garbage, in code, free.
2. narrow — one model call that judges relevance, in one of two candidate
   ways chosen by settings.context_mode:

   select  the model names which numbered fragments help; those go to the
           answer verbatim, so every citation points at the very text the
           answer was written from.
   digest  the model writes a condensed extract from the fragments; the
           answer reads fewer tokens, but a number misread here reaches it
           under a real citation.

Both are kept until evals/compare_context_modes.py has shown which answers
better. Both are strictly optional: a call that fails or answers with
something unreadable leaves the request on everything it retrieved.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core.llm_provider import Completion, complete
from app.core.prompts import DIGEST_INSTRUCTIONS, SELECT_INSTRUCTIONS, build_narrowing_messages
from app.core.tools import (
    PICK_FRAGMENTS,
    PICK_FRAGMENTS_TOOL,
    WRITE_EXTRACT,
    WRITE_EXTRACT_TOOL,
    parse_extract,
    parse_picked_fragments,
)

_log = logging.getLogger(__name__)

_CITATION = re.compile(r"\[(\d+)\]")


@dataclass
class RulesContext:
    """What the answer is built from.

    chunks are the pages behind the answer and what its sources are listed
    from. digest, when set, is what the answering model reads in their place.
    """

    chunks: list[dict[str, Any]]
    digest: str | None = None


def within_distance(retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    limit = settings.retrieval_max_distance
    kept = [hit for hit in retrieved if hit["distance"] <= limit]
    if len(kept) < len(retrieved):
        _log.info("distance cut: kept %d of %d hits within %.2f", len(kept), len(retrieved), limit)
    return kept


def _ask(question: str, retrieved: list[dict[str, Any]]) -> Completion:
    if settings.context_mode == "select":
        instructions, tool = SELECT_INSTRUCTIONS, PICK_FRAGMENTS_TOOL
    else:
        instructions, tool = DIGEST_INSTRUCTIONS, WRITE_EXTRACT_TOOL
    return complete(build_narrowing_messages(instructions, question, retrieved), tools=[tool])


def _selected(completion: Completion, retrieved: list[dict[str, Any]]) -> RulesContext:
    raw = completion.tool_arguments.get(PICK_FRAGMENTS)
    picked = parse_picked_fragments(raw, len(retrieved)) if raw else None
    if picked is None:
        _log.warning("fragment selection unreadable; keeping all %d hits", len(retrieved))
        return RulesContext(retrieved)
    main, related = picked
    # Main first: the answering model reads the front of its context most
    # closely. Related pages follow because they were read, so they belong
    # in the sources under the answer too.
    return RulesContext([retrieved[number - 1] for number in main + related])


def _digested(completion: Completion, retrieved: list[dict[str, Any]]) -> RulesContext:
    raw = completion.tool_arguments.get(WRITE_EXTRACT)
    parsed = parse_extract(raw, len(retrieved)) if raw else None
    if parsed is None:
        _log.warning("rules extract unreadable; keeping all %d hits", len(retrieved))
        return RulesContext(retrieved)

    extract, used = parsed
    if not used:
        return RulesContext([])

    # The extract cites the fragments as they were numbered for it; the
    # answer sees only the used ones, numbered afresh.
    renumbered = {old: new for new, old in enumerate(used, 1)}

    def _cite(match: re.Match[str]) -> str:
        new = renumbered.get(int(match.group(1)))
        return f"[{new}]" if new else match.group(0)

    return RulesContext(
        [retrieved[number - 1] for number in used], digest=_CITATION.sub(_cite, extract)
    )


def narrow(question: str, retrieved: list[dict[str, Any]]) -> RulesContext:
    """The hits that bear on *question*, per settings.context_mode.

    Never raises, and makes no call when there is nothing to judge.
    """
    if settings.context_mode == "off" or not retrieved:
        return RulesContext(retrieved)

    try:
        completion = _ask(question, retrieved)
    except Exception as exc:  # noqa: BLE001 — narrowing is strictly optional
        _log.warning(
            "context %s unavailable (%s); keeping all %d hits",
            settings.context_mode,
            type(exc).__name__,
            len(retrieved),
        )
        return RulesContext(retrieved)

    if settings.context_mode == "select":
        context = _selected(completion, retrieved)
    else:
        context = _digested(completion, retrieved)
    _log.info(
        "context %s: kept %d of %d hits %s",
        settings.context_mode,
        len(context.chunks),
        len(retrieved),
        [hit["metadata"]["title"] for hit in context.chunks],
    )
    return context


__all__ = ["RulesContext", "narrow", "within_distance"]
