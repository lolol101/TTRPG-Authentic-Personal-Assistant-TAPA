from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from app.core.embedding_provider import EmbeddingProvider, get_embedding_provider
from app.core.vector_store import upsert

_log = logging.getLogger(__name__)
_BATCH_SIZE = 32


def load_records(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def to_metadata(record: dict[str, Any]) -> dict[str, Any]:
    """Chroma metadata values must be str/int/float/bool — no None, no lists."""
    return {
        "url": record["url"],
        "title": record["title"],
        "category": record["category"],
        "source_book": record.get("source_book") or "",
        "traits": ", ".join(record.get("traits") or []),
        "language": record.get("language", "ru"),
    }


def ingest_records(records: list[dict[str, Any]], provider: EmbeddingProvider) -> int:
    total = 0
    for start in range(0, len(records), _BATCH_SIZE):
        batch = records[start : start + _BATCH_SIZE]
        embeddings = provider.embed([r["text"] for r in batch])
        upsert(
            ids=[r["id"] for r in batch],
            embeddings=embeddings,
            documents=[r["text"] for r in batch],
            metadatas=[to_metadata(r) for r in batch],
        )
        total += len(batch)
        _log.info("Indexed %d/%d chunks", total, len(records))
    return total


def ingest_file(path: Path, provider: EmbeddingProvider) -> int:
    return ingest_records(load_records(path), provider)


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed chunk .jsonl files into the Chroma store.")
    parser.add_argument("paths", nargs="+", help="One or more chunk .jsonl files to ingest")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    provider = get_embedding_provider()
    total = sum(ingest_file(Path(p), provider) for p in args.paths)
    print(f"Indexed {total} chunks total.")


if __name__ == "__main__":
    main()
