"""Lifts the local SQLite database into a cloud Postgres.

Run it from apps/web-backend so the app's own settings and models are on the
path:

    cd apps/web-backend
    uv run python ../../scripts/migrate_to_postgres.py \
        --to "postgresql+psycopg://user:pass@host/db?sslmode=require"

The source defaults to whatever DATABASE_URL the app is configured with, so
in practice you only pass the destination. Stop the backend first: copying a
SQLite file that is being written to can capture a half-finished write.

Afterwards, point DATABASE_URL at the same Postgres URL and restart.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Run from apps/web-backend, where the app package lives.
sys.path.insert(0, str(Path.cwd()))

from sqlmodel import create_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.migrate import TargetNotEmptyError, copy_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", required=True, metavar="URL", help="Destination database URL")
    parser.add_argument(
        "--from",
        dest="source",
        default=None,
        help="Source URL (default: the app's own DATABASE_URL)",
    )
    parser.add_argument(
        "--allow-nonempty",
        action="store_true",
        help="Copy even if the destination already holds rows (risks duplicates)",
    )
    args = parser.parse_args()

    source_url = args.source or settings.database_url
    print(f"Откуда: {source_url}")
    print(f"Куда:   {_redact(args.to)}")

    source = create_engine(source_url)
    target = create_engine(args.to)

    try:
        results = copy_database(source, target, allow_nonempty=args.allow_nonempty)
    except TargetNotEmptyError as exc:
        print(f"\nОтменено: {exc}")
        return 1

    print()
    for result in results:
        print(f"  {result.table}: {result.copied} строк")
    print("\nГотово. Теперь укажи этот URL в DATABASE_URL и перезапусти бэкенд.")
    return 0


def _redact(url: str) -> str:
    """Connection strings carry the password; do not print it."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    credentials, host = rest.split("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
