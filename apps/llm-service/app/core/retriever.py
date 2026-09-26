from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from app.core.config import settings
from app.core.embedding_provider import get_embedding_provider
from app.core.vector_store import query as vector_query

_log = logging.getLogger(__name__)


def retrieve(
    question: str,
    k: int | None = None,
    ruleset: str | None = None,
    categories: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """The *k* rule chunks nearest to *question*.

    *categories* narrows the search to the parts of the corpus that can
    answer it — see sheet_plan.AREA_CATEGORIES. A narrowed search that comes
    back short is topped up from the whole index: the category comes from the
    model naming an area, and a wrong name must not be able to turn a request
    into "the rules say nothing". The filtered hits stay in front, where the
    model reads most closely.
    """
    wanted = k or settings.retrieval_k
    provider = get_embedding_provider()
    embedding = provider.embed([question])[0]

    if not categories:
        return vector_query(embedding, wanted, ruleset=ruleset)

    hits = vector_query(embedding, wanted, ruleset=ruleset, categories=categories)
    if len(hits) >= wanted:
        return hits

    # Short: either the section is genuinely smaller than k, or the area was
    # named wrongly. Either way the same embedding is reused, so the top-up
    # costs one index lookup and no model call.
    _log.info(
        "section filter %s returned %d of %d; topping up from the whole index",
        list(categories),
        len(hits),
        wanted,
    )
    seen = {hit["id"] for hit in hits}
    for hit in vector_query(embedding, wanted, ruleset=ruleset):
        if hit["id"] in seen:
            continue
        hits.append(hit)
        if len(hits) == wanted:
            break
    return hits


def is_weak(retrieved: list[dict[str, Any]]) -> bool:
    """Whether nothing retrieved is a confident match for the question.

    Empty context already reads as "(контекст не найден)" in the prompt —
    this catches the quieter failure: *k* chunks came back, because Chroma
    always returns its *k* nearest regardless of how far they are, and nudged
    into a plausible-sounding answer whose citation does not actually say it.
    The closest hit's distance is what tells the two apart; see
    settings.retrieval_weak_distance for how that number was measured.
    """
    if not retrieved:
        return True
    return min(hit["distance"] for hit in retrieved) > settings.retrieval_weak_distance
