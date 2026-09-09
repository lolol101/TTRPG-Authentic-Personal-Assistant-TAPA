"""Archives of Nethys page scraper.

Typical usage:

    scraper = AonScraper(book_name="pf2e")
    pages = await scraper.scrape_source_page("https://2e.aonprd.com/Sources.aspx")

Each returned page is a tuple (title, html_content) suitable for the existing
ingestion pipeline (services.html / services.text_processing).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from config.settings import settings

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": "TAPA-Bot/0.1 (TTRPG research assistant; +https://github.com)"
}


class AonScraper:
    """Scrape Archives of Nethys HTML pages for a given book."""

    def __init__(
        self,
        book_name: str,
        cache_dir: str | None = None,
        rate_limit: float | None = None,
    ) -> None:
        self.book_name = book_name
        self.cache_dir = Path(cache_dir or settings.scraper_cache_dir) / book_name
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit = rate_limit or settings.scraper_rate_limit

    def _cache_path(self, url: str) -> Path:
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.html"

    def _read_cache(self, url: str) -> str | None:
        path = self._cache_path(url)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def _write_cache(self, url: str, html: str) -> None:
        path = self._cache_path(url)
        path.write_text(html, encoding="utf-8")

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str:
        cached = self._read_cache(url)
        if cached is not None:
            logger.debug("Cache hit: %s", url)
            return cached

        logger.info("Fetching: %s", url)
        resp = await client.get(url, headers=_DEFAULT_HEADERS, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        self._write_cache(url, html)

        await asyncio.sleep(self.rate_limit)
        return html

    def _extract_links(self, base_url: str, html: str) -> list[str]:
        """Extract internal page links from an AoN page."""
        soup = BeautifulSoup(html, "lxml")
        base_parsed = urlparse(base_url)
        links: list[str] = []
        for a_tag in soup.find_all("a", href=True):
            href: str = a_tag["href"]
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            if parsed.netloc != base_parsed.netloc:
                continue
            if not parsed.path.lower().endswith(".aspx"):
                continue
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"
            links.append(clean_url)
        return list(dict.fromkeys(links))

    @staticmethod
    def _title_from_html(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip()
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return "Untitled"

    async def scrape_source_page(
        self,
        source_url: str,
        max_pages: int = 0,
    ) -> list[tuple[str, str]]:
        """Scrape an AoN Sources page and all pages linked from it.

        Returns a list of (title, raw_html) tuples.
        Set *max_pages* > 0 to cap the number of sub-pages fetched (useful for
        testing).
        """
        results: list[tuple[str, str]] = []

        async with httpx.AsyncClient(timeout=30) as client:
            index_html = await self._fetch(client, source_url)
            child_urls = self._extract_links(source_url, index_html)

            if max_pages > 0:
                child_urls = child_urls[:max_pages]

            logger.info(
                "Found %d links on %s (processing %d)",
                len(child_urls),
                source_url,
                len(child_urls),
            )

            for url in child_urls:
                try:
                    html = await self._fetch(client, url)
                    title = self._title_from_html(html)
                    results.append((title, html))
                except httpx.HTTPError:
                    logger.warning("Failed to fetch: %s", url, exc_info=True)

        return results
