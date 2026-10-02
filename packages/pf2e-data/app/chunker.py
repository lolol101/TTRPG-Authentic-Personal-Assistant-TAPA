from __future__ import annotations

import hashlib

from app.core.config import settings
from app.models import Chunk, ParsedPage


def chunk_page(
    page: ParsedPage, max_chars: int | None = None, language: str = "ru"
) -> list[Chunk]:
    """Turn one parsed page into one or more retrievable chunks.

    Most pf2.ru action pages are short and produce exactly one chunk; longer
    pages are split on paragraph breaks so no chunk exceeds *max_chars*.

    *language* rides along into the index because the corpus is no longer
    single-language: pf2.ru is Russian, the Foundry packs are English, and an
    answer's language should be explicable from the chunk it came from.
    """
    max_chars = max_chars or settings.max_chunk_chars
    parts = _split_on_paragraphs(page.body, max_chars) or [page.body]

    # Measured 2026-10-01: a continuation chunk carried no word of what page
    # it came from, and "fire domain cleric" never found the Fire Domain
    # page. Each one after the first now opens with the title, and the body
    # is split with room left for it so no chunk outgrows max_chars.
    heading = f"{page.title}\n\n" if page.title else ""
    if len(parts) > 1 and heading and len(heading) < max_chars // 2:
        parts = _split_on_paragraphs(page.body, max_chars - len(heading)) or [page.body]
        parts = parts[:1] + [heading + part for part in parts[1:]]

    base_id = hashlib.sha256(page.url.encode("utf-8")).hexdigest()[:16]
    single = len(parts) == 1
    return [
        Chunk(
            id=base_id if single else f"{base_id}-{index}",
            url=page.url,
            category=page.category,
            title=page.title,
            source_book=page.source_book,
            traits=list(page.traits),
            language=page.language or language,
            text=part,
            license=page.license,
            translation_source=page.translation_source,
            translation_license=page.translation_license,
        )
        for index, part in enumerate(parts)
    ]


def _split_on_paragraphs(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text] if text else []

    parts: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in text.split("\n"):
        addition = len(paragraph) + 1
        if current and current_len + addition > max_chars:
            parts.append("\n".join(current))
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += addition

    if current:
        parts.append("\n".join(current))

    return parts
