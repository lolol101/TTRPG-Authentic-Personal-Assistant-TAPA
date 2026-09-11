"""Offline stage for D&D 5e: SRD PDF -> text -> chunks -> jsonl.

Deliberately mirrors packages/pf2e-data: same offline/online split, same
chunk shape, so llm-service ingests both without knowing the difference.
The only thing that distinguishes them downstream is `ruleset`, which is
what makes a D&D question search D&D rules.

The SRD is one PDF rather than a site, so there is no crawler here — the
file is downloaded once and parsed from disk.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.config import settings

_log = logging.getLogger(__name__)

#: Page headers and footers repeat on every page and add nothing to a chunk.
_NOISE = re.compile(r"^\s*(System Reference Document 5\.2\.1|\d+)\s*$", re.MULTILINE)

#: An SRD heading: a short line in title case with no sentence punctuation.
_HEADING = re.compile(r"^(?!.*[.;:,])([A-Z][A-Za-z'’\- ]{2,60})$")

#: Table-of-contents lines: a title, dotted leaders, a page number. They read
#: as prose to the chunker and as noise to a reader.
_TOC_LINE = re.compile(r"\.{4,}\s*\d+")


@dataclass
class Chunk:
    id: str
    url: str
    category: str
    title: str
    source_book: str
    traits: list[str]
    language: str
    ruleset: str
    text: str


def extract_pages(pdf_path: Path, first: int = 0, last: int | None = None) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = reader.pages[first:last] if last is not None else reader.pages[first:]
    return [_NOISE.sub("", page.extract_text() or "").strip() for page in pages]


def split_sections(pages: list[str]) -> list[tuple[str, str]]:
    """Groups the running text under the last heading seen.

    A PDF carries no structure worth trusting, so headings are recognised by
    shape. Anything before the first heading belongs to no section and is
    dropped rather than filed under a wrong title.
    """
    sections: list[tuple[str, list[str]]] = []
    for page in pages:
        for line in page.splitlines():
            stripped = line.strip()
            if not stripped or _TOC_LINE.search(stripped):
                continue
            if _HEADING.match(stripped) and len(stripped.split()) <= 6:
                sections.append((stripped, []))
            elif sections:
                sections[-1][1].append(stripped)

    return [(title, " ".join(body)) for title, body in sections if body]


def chunk_sections(sections: list[tuple[str, str]], max_chars: int | None = None) -> list[Chunk]:
    limit = max_chars or settings.max_chunk_chars
    chunks: list[Chunk] = []

    for position, (title, body) in enumerate(sections):
        for index, piece in enumerate(_split_text(body, limit)):
            # Headings repeat across the SRD ("Ability Descriptions" appears
            # more than once), so the section's position is part of the key.
            # The SRD has no per-rule URLs, so every chunk points at the
            # document itself — the reader still needs somewhere to verify.
            key = f"{position}:{title}:{index}"
            identifier = hashlib.sha256(key.encode()).hexdigest()[:16]
            chunks.append(
                Chunk(
                    id=f"dnd5e-{identifier}",
                    url="https://www.dndbeyond.com/srd",
                    category="srd",
                    title=title,
                    source_book=settings.source_book,
                    traits=[],
                    language="en",
                    ruleset="dnd5e",
                    text=f"{title}. {piece}",
                )
            )
    return chunks


def _split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]

    pieces: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.!?]) ", text):
        if current and len(current) + len(sentence) + 1 > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def run(*, first_page: int = 0, last_page: int | None = None) -> Path:
    pdf_path = Path(settings.source_dir) / settings.srd_filename
    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"SRD не найден: {pdf_path}. Скачай его: {settings.srd_url}"
        )

    pages = extract_pages(pdf_path, first_page, last_page)
    sections = split_sections(pages)
    chunks = chunk_sections(sections)
    _log.info("Pages %s-%s -> %d sections -> %d chunks", first_page, last_page, len(sections),
              len(chunks))

    out_path = Path(settings.output_dir) / "srd.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")

    return out_path
