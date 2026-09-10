from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from app.chunker import chunk_page
from app.core.config import settings
from app.parser import UnrecognizedPageError, parse_page
from app.scraper import Scraper
from app.sitemap import fetch_sitemap_urls, filter_by_prefix

_log = logging.getLogger(__name__)


def run(*, path_prefix: str, limit: int | None = None, output_dir: str | None = None) -> Path:
    """Offline stage: sitemap -> scrape (cached) -> parse -> chunk -> jsonl.

    Deterministic and re-runnable: the same sitemap + prefix + limit always
    selects the same URLs (sitemap order), and cached HTML means a re-run
    doesn't re-fetch pages already on disk.
    """
    urls = fetch_sitemap_urls(settings.sitemap_url, user_agent=settings.user_agent)
    selected = filter_by_prefix(urls, path_prefix=path_prefix, limit=limit)
    _log.info("Selected %d/%d sitemap URLs matching %s", len(selected), len(urls), path_prefix)

    scraper = Scraper()
    out_path = Path(output_dir or settings.output_dir) / f"{path_prefix.strip('/')}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for raw_page in scraper.fetch_all(selected):
            try:
                parsed = parse_page(raw_page)
            except UnrecognizedPageError as exc:
                _log.warning("Skipping %s: %s", raw_page.url, exc)
                skipped += 1
                continue
            for chunk in chunk_page(parsed):
                fh.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
                written += 1

    _log.info("Wrote %d chunks (%d pages skipped) to %s", written, skipped, out_path)
    return out_path
