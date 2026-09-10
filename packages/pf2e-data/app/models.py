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
