from __future__ import annotations

import hashlib

from app.core.config import settings
from app.models import Chunk, ParsedPage


def chunk_page(page: ParsedPage, max_chars: int | None = None) -> list[Chunk]:
    """Turn one parsed page into one or more retrievable chunks.

    Most pf2.ru action pages are short and produce exactly one chunk; longer
    pages are split on paragraph breaks so no chunk exceeds *max_chars*.
    """
    max_chars = max_chars or settings.max_chunk_chars
    parts = _split_on_paragraphs(page.body, max_chars) or [page.body]

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
            text=part,
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
