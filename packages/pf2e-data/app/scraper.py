from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.core.config import settings
from app.models import RawPage

_log = logging.getLogger(__name__)


def _is_refusal(exc: Exception) -> bool:
    """403 and 429 mean "not you, not now" — everything else is about the page."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status in (403, 429)


def _describe(exc: Exception) -> str:
    """Status-code failures print their whole help URL; keep the log readable."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return f"HTTP {status}" if status else f"{type(exc).__name__}: {exc}"


#: Consecutive refusals that mean the site has stopped serving us rather
#: than that these particular pages are gone.
_BLOCK_STREAK = 10


class SiteBlockedError(RuntimeError):
    """pf2.ru is refusing this crawler, not missing these pages."""


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
        self._unreachable: list[str] = []

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

    def fetch_all(self, urls: list[str]) -> Iterator[RawPage]:
        """Yields pages as they arrive, skipping the ones that cannot be had.

        Two reasons not to collect first and not to stop on every failure: a
        full section runs to thousands of pages of a few hundred KB each, so
        holding them all would cost about a gigabyte before parsing starts;
        and the sitemap lists URLs that now answer 404 or 500, so one dead
        link must not throw away the several hundred pages behind it.

        A run of refusals is the opposite case and has to end the section.
        pf2.ru rate-limits this crawler by answering 403, and skipping
        through that marks every remaining page unreachable and reports the
        section finished — a spells run lost 1306 live pages that way. The
        pages are still there; we are simply not welcome for the moment, and
        the right answer is to stop and come back.
        """
        blocked_streak = 0
        with httpx.Client() as client:
            for url in urls:
                try:
                    page = self.fetch(url, client)
                except httpx.HTTPError as exc:
                    _log.warning("Skipping %s: %s", url, _describe(exc))
                    self._unreachable.append(url)
                    if _is_refusal(exc):
                        blocked_streak += 1
                        if blocked_streak >= _BLOCK_STREAK:
                            raise SiteBlockedError(
                                f"pf2.ru отказал {blocked_streak} раз подряд — "
                                "похоже на блокировку. Останавливаюсь, чтобы не "
                                "пометить остальные страницы как недоступные."
                            ) from exc
                    continue

                blocked_streak = 0
                yield page

    @property
    def unreachable(self) -> list[str]:
        """URLs that failed this run — worth reporting, not worth crashing on."""
        return list(self._unreachable)

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
