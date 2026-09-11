"""Checks that a transferred data folder is complete and usable.

Run it after copying the data to another machine, before starting anything:
finding out here beats finding out from an empty character list.

    python scripts/check_data.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILES = [
    REPO_ROOT / "apps" / "web-backend" / ".env",
    REPO_ROOT / "apps" / "llm-service" / ".env",
    REPO_ROOT / "packages" / "pf2e-data" / ".env",
]


def read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    problems: list[str] = []
    notes: list[str] = []

    envs = {path: read_env(path) for path in ENV_FILES}
    for path, values in envs.items():
        if not values:
            problems.append(f"нет файла {path.relative_to(REPO_ROOT)} — скопируй его со старой машины")

    roots = {values.get("TAPA_DATA_DIR") for values in envs.values() if values}
    roots.discard(None)
    if len(roots) > 1:
        problems.append(f"TAPA_DATA_DIR отличается между .env: {sorted(roots)}")

    root_value = os.environ.get("TAPA_DATA_DIR") or (next(iter(roots), None) if roots else None)
    if not root_value:
        notes.append("TAPA_DATA_DIR не задан — данные ищутся рядом с каждым сервисом в ./data")
        return report(problems, notes)

    root = Path(root_value)
    print(f"Корень данных: {root}")
    if not root.is_dir():
        problems.append(f"папки {root} не существует — скопирована ли она?")
        return report(problems, notes)

    database = root / "web-backend" / "dev.db"
    if not database.is_file():
        problems.append(f"нет базы {database} — персонажи и аккаунты не переедут")
    else:
        try:
            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
            users = connection.execute("select count(*) from user").fetchone()[0]
            characters = connection.execute("select count(*) from character").fetchone()[0]
            connection.close()
            print(f"База: {users} пользователей, {characters} персонажей")
        except sqlite3.Error as exc:
            problems.append(f"база не читается ({exc}) — возможно, скопирована во время записи")

    index = root / "llm-service" / "vector_db"
    if not index.is_dir():
        notes.append("нет индекса llm-service/vector_db — пересоберётся из chunks за минуты")

    chunks = list((root / "pf2e-data" / "chunks").glob("*.jsonl"))
    if not chunks:
        notes.append("нет pf2e-data/chunks — поиск по правилам работать не будет")
    else:
        print(f"Чанки: {len(chunks)} файлов")

    cache = root / "pf2e-data" / "html_cache"
    if not cache.is_dir():
        notes.append("нет html_cache — пересборка потребует повторного скачивания (часы)")

    if not envs.get(ENV_FILES[0], {}).get("JWT_SECRET_KEY"):
        problems.append("в web-backend/.env нет JWT_SECRET_KEY — приложение не стартует")

    return report(problems, notes)


def report(problems: list[str], notes: list[str]) -> int:
    for note in notes:
        print(f"[замечание] {note}")
    for problem in problems:
        print(f"[ПРОБЛЕМА]  {problem}")
    if problems:
        print(f"\nНе готово: {len(problems)} проблем.")
        return 1
    print("\nВсё на месте.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
