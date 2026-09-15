from __future__ import annotations

from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def parse_sitemap_urls(xml_text: str) -> list[str]:
    """Extract every <loc> URL from a sitemap.xml document, in document order."""
    root = ElementTree.fromstring(xml_text)
    return [loc.text.strip() for loc in root.findall(".//sm:loc", _SITEMAP_NS) if loc.text]


def fetch_sitemap_urls(sitemap_url: str, *, user_agent: str, timeout: float = 30.0) -> list[str]:
    response = httpx.get(sitemap_url, headers={"User-Agent": user_agent}, timeout=timeout)
    response.raise_for_status()
    return parse_sitemap_urls(response.text)


def filter_by_prefix(urls: list[str], *, path_prefix: str, limit: int | None = None) -> list[str]:
    """Keep URLs whose path starts with *path_prefix* (e.g. "/actions/"), in order.

    Repeats are dropped: pf2.ru lists a good many pages more than once, and
    fetching those twice cost about a quarter of every crawl against a site
    that rate-limits — besides writing the same chunk into the index twice.

    *limit* caps how many are returned — first N in sitemap order, so the
    selection is deterministic and reproducible across runs.
    """
    matched: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if not _path_of(url).startswith(path_prefix) or url in seen:
            continue
        seen.add(url)
        matched.append(url)
    return matched[:limit] if limit is not None else matched


def _path_of(url: str) -> str:
    return urlparse(url).path
