from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.core.config import settings
from app.models import RawPage

_log = logging.getLogger(__name__)


class RefusalPageError(httpx.HTTPError):
    """pf2.ru answered 200 with its "suspicious activity" page instead of the rule."""


def is_refusal(exc: Exception) -> bool:
    """403, 429 and the refusal page mean "not you, not now" — everything
    else is about the page.

    Public so app.sitemap can classify a blocked sitemap.xml the same way —
    the block is site-wide and hits that URL just as it hits any page.
    """
    if isinstance(exc, RefusalPageError):
        return True
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status in (403, 429)


def _describe(exc: Exception) -> str:
    """Status-code failures print their whole help URL; keep the log readable."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return f"HTTP {status}" if status else f"{type(exc).__name__}: {exc}"


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
        *,
        refusal_backoff_seconds: float | None = None,
        refusal_backoff_max_seconds: float | None = None,
        refusal_max_wait_seconds: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit_seconds = rate_limit_seconds or settings.rate_limit_seconds
        self.user_agent = user_agent or settings.user_agent
        self.refusal_backoff_seconds = _or_default(
            refusal_backoff_seconds, settings.refusal_backoff_seconds
        )
        self.refusal_backoff_max_seconds = _or_default(
            refusal_backoff_max_seconds, settings.refusal_backoff_max_seconds
        )
        self.refusal_max_wait_seconds = _or_default(
            refusal_max_wait_seconds, settings.refusal_max_wait_seconds
        )
        self._sleep = sleep
        self._unreachable: list[str] = []

    def fetch(self, url: str, client: httpx.Client) -> RawPage:
        cached = self._read_cache(url)
        if cached is not None:
            return cached

        response = client.get(url, headers={"User-Agent": self.user_agent}, timeout=30.0)
        response.raise_for_status()
        if _is_refusal_page(response.text):
            raise RefusalPageError(f"refusal page instead of {url}")
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

        A refusal (403/429) is the opposite case: the page is there, we are
        just not welcome for the moment. Skipping it loses the page — a
        spells run lost 1306 that way, and a later run skipped every uncached
        page because the cached ones in between hid the block. So a refused
        page is waited for, and only a refusal that outlasts the patience
        ends the section.
        """
        with httpx.Client() as client:
            for url in urls:
                try:
                    page = self._fetch_waiting_out_refusals(url, client)
                except httpx.HTTPError as exc:
                    _log.warning("Skipping %s: %s", url, _describe(exc))
                    self._unreachable.append(url)
                    continue
                yield page

    def _fetch_waiting_out_refusals(self, url: str, client: httpx.Client) -> RawPage:
        waited = 0.0
        wait = self.refusal_backoff_seconds
        while True:
            try:
                return self.fetch(url, client)
            except httpx.HTTPError as exc:
                if not is_refusal(exc):
                    raise
                if waited + wait > self.refusal_max_wait_seconds:
                    raise SiteBlockedError(
                        f"pf2.ru не пускает уже {_format_wait(waited)} на {url} — "
                        "похоже на блокировку. Останавливаюсь, чтобы не "
                        "пометить остальные страницы как недоступные."
                    ) from exc
                _log.warning(
                    "%s on %s, waiting %s before retrying", _describe(exc), url, _format_wait(wait)
                )
                self._sleep(wait)
                waited += wait
                wait = min(wait * 2, self.refusal_backoff_max_seconds)

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
        html = path.read_text(encoding="utf-8")
        if _is_refusal_page(html):
            # Cached by crawlers that took the 200 at face value; 1200 of the
            # first 2921 cached pages were this, not rules.
            path.unlink()
            return None
        fetched_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        return RawPage(url=url, html=html, fetched_at=fetched_at)

    def _write_cache(self, page: RawPage) -> None:
        self._cache_path(page.url).write_text(page.html, encoding="utf-8")


def _is_refusal_page(html: str) -> bool:
    return settings.refusal_page_marker in html


def _format_wait(seconds: float) -> str:
    return f"{seconds / 60:.0f} мин" if seconds >= 60 else f"{seconds:.0f} с"


def _or_default(value: float | None, default: float) -> float:
    """Zero is a meaningful setting here (no patience), so `or` would not do."""
    return default if value is None else value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
