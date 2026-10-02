from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawPage:
    """A single fetched (and cached) HTML page, not yet parsed."""

    url: str
    html: str
    fetched_at: str  # ISO 8601 UTC timestamp


@dataclass
class ParsedPage:
    """Cleaned, structured content extracted from one RawPage."""

    url: str
    category: str
    title: str
    source_book: str | None
    traits: list[str]
    body: str
    fetched_at: str
    # Where the text's openness comes from: the stamp a source put on it
    # ("ORC", "OGL"), "unstamped" for text indexed without one, empty where
    # the source has no such notion (the pf2.ru crawl).
    license: str = ""
    # None leaves the language to whoever chunks the page; set when one source
    # yields pages in two languages, as the packs do with a translation laid
    # over them.
    language: str | None = None
    # Who translated the text and under what terms — separate from `license`,
    # which stays the original's (docs/rfc/0001). Empty for untranslated text.
    translation_source: str = ""
    translation_license: str = ""


@dataclass
class Chunk:
    """One retrievable unit, ready to be embedded and stored."""

    id: str
    url: str
    category: str
    title: str
    source_book: str | None
    traits: list[str] = field(default_factory=list)
    language: str = "ru"
    text: str = ""
    license: str = ""
    translation_source: str = ""
    translation_license: str = ""
