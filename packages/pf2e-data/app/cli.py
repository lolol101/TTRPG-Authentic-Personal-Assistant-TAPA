from __future__ import annotations

import argparse
import logging

from app.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl and chunk PF2e content from pf2.ru.")
    parser.add_argument(
        "--prefix",
        default="actions",
        help="Sitemap path segment to ingest, e.g. actions (default: %(default)s)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="Max pages to ingest, first N in sitemap order (default: %(default)s)",
    )
    parser.add_argument("--output-dir", default=None, help="Override the chunk output directory")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    path_prefix = f"/{args.prefix.strip('/')}/"
    out_path = run(path_prefix=path_prefix, limit=args.limit, output_dir=args.output_dir)
    print(f"Wrote chunks to {out_path}")


if __name__ == "__main__":
    main()
