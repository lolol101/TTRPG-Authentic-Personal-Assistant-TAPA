from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.core.config import settings
from app.models import RawPage


class Scraper:
    """Rate-limited, disk-cached fetcher. A re-run over the same URLs makes
    no new HTTP requests — courteous to pf2.ru and reproducible for us.
    """

    def __init__(
        self,
        cache_dir: str | None = None,
        rate_limit_seconds: float | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit_seconds = rate_limit_seconds or settings.rate_limit_seconds
        self.user_agent = user_agent or settings.user_agent

    def fetch(self, url: str, client: httpx.Client) -> RawPage:
        cached = self._read_cache(url)
        if cached is not None:
            return cached

        response = client.get(url, headers={"User-Agent": self.user_agent}, timeout=30.0)
        response.raise_for_status()
        page = RawPage(url=url, html=response.text, fetched_at=_now_iso())
        self._write_cache(page)
        time.sleep(self.rate_limit_seconds)
        return page

    def fetch_all(self, urls: list[str]) -> list[RawPage]:
        pages = []
        with httpx.Client() as client:
            for url in urls:
                pages.append(self.fetch(url, client))
        return pages

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.html"

    def _read_cache(self, url: str) -> RawPage | None:
        path = self._cache_path(url)
        if not path.exists():
            return None
        fetched_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        return RawPage(url=url, html=path.read_text(encoding="utf-8"), fetched_at=fetched_at)

    def _write_cache(self, page: RawPage) -> None:
        self._cache_path(page.url).write_text(page.html, encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
