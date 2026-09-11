"""Ingests every pf2.ru section the parser can currently read.

A full pass is thousands of pages at one request per second, so this is a
run-it-overnight job, not something to sit and watch. The HTML cache makes a
second pass cheap, which is what makes it safe to stop and resume.

    uv run python -m app.corpus            # everything that parses
    uv run python -m app.corpus --only feats spells
    uv run python -m app.corpus --limit 20 # a smoke run over every section

Sections the parser does NOT handle yet (ancestries, classes, rituals,
hazards, armor) are deliberately absent — including them would write empty
files and hide the gap. See docs/BACKLOG.md.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from app.core.config import settings
from app.pipeline import run
from app.progress import Progress, format_duration
from app.sitemap import fetch_sitemap_urls, filter_by_prefix

#: Smallest first: a broad failure shows up in minutes instead of hours.
SECTIONS: list[str] = [
    "archetypes",
    "heritages",
    "backgrounds",
    "weapons",
    "deities",
    "actions",
    "traits",
    "classfeatures",
    "monsters",
    "spells",
    "equipment",
    "feats",
]

_log = logging.getLogger("corpus")


def count_pages(sections: list[str], limit: int | None) -> dict[str, int]:
    """How many pages each section holds, from a single sitemap fetch.

    Known upfront so the estimate covers the whole run: "when can I stop
    watching" is the question worth answering, not "when does feats end".
    """
    urls = fetch_sitemap_urls(settings.sitemap_url, user_agent=settings.user_agent)
    return {
        section: len(filter_by_prefix(urls, path_prefix=f"/{section}/", limit=limit))
        for section in sections
    }


def ingest(sections: list[str], limit: int | None) -> int:
    failures = 0
    started = time.monotonic()

    print("Считаю объём по sitemap…", flush=True)
    per_section = count_pages(sections, limit)
    overall_total = sum(per_section.values())
    print(f"К обработке {overall_total} страниц в {len(sections)} разделах.\n", flush=True)

    overall_done = 0
    for index, section in enumerate(sections, start=1):
        progress = Progress(
            f"[{index}/{len(sections)}] {section}",
            per_section[section],
            overall_done=overall_done,
            overall_total=overall_total,
            started_at=started,
        )
        try:
            out_path = run(path_prefix=f"/{section}/", limit=limit, on_page=progress.advance)
        except Exception as exc:  # noqa: BLE001 — one bad section must not end the run
            failures += 1
            print(f"\n{section}: ОШИБКА {type(exc).__name__}: {exc}", flush=True)
            overall_done += per_section[section]
            continue

        progress.finish()
        overall_done = progress.overall_done
        lines = sum(1 for _ in out_path.open(encoding="utf-8"))
        print(f"    {section}: {lines} чанков -> {out_path}", flush=True)

    print(
        f"\nГотово за {format_duration(time.monotonic() - started)}, "
        f"разделов с ошибкой: {failures}",
        flush=True,
    )
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", metavar="SECTION", help="Ingest just these sections")
    parser.add_argument("--limit", type=int, default=None, help="Cap pages per section")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    sections = args.only or SECTIONS
    unknown = [name for name in sections if name not in SECTIONS]
    if unknown:
        print(f"Неизвестные разделы: {unknown}. Доступны: {SECTIONS}")
        return 2

    return ingest(sections, args.limit)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
