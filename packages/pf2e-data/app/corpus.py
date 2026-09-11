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

from app.pipeline import run

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


def ingest(sections: list[str], limit: int | None) -> int:
    failures = 0
    started = time.monotonic()

    for index, section in enumerate(sections, start=1):
        section_started = time.monotonic()
        print(f"[{index}/{len(sections)}] {section}: старт", flush=True)
        try:
            out_path = run(path_prefix=f"/{section}/", limit=limit)
        except Exception as exc:  # noqa: BLE001 — one bad section must not end the run
            failures += 1
            print(f"[{index}/{len(sections)}] {section}: ОШИБКА {type(exc).__name__}: {exc}",
                  flush=True)
            continue

        lines = sum(1 for _ in out_path.open(encoding="utf-8"))
        elapsed = time.monotonic() - section_started
        print(
            f"[{index}/{len(sections)}] {section}: {lines} чанков за {elapsed / 60:.1f} мин "
            f"-> {out_path}",
            flush=True,
        )

    minutes = (time.monotonic() - started) / 60
    print(f"\nГотово за {minutes:.1f} мин, разделов с ошибкой: {failures}", flush=True)
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
