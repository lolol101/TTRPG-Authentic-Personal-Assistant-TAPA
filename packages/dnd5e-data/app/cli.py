"""Turns the SRD PDF into chunks.

    uv run python -m app.cli --last-page 40

The SRD is 360-odd pages; a page range keeps a trial run quick while still
producing something real to search.
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-page", type=int, default=0)
    parser.add_argument("--last-page", type=int, default=None, help="Exclusive; omit for all")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    out_path = run(first_page=args.first_page, last_page=args.last_page)
    lines = sum(1 for _ in out_path.open(encoding="utf-8"))
    print(f"{lines} чанков -> {out_path}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
