"""Copies the whole database from one engine to another.

Used to lift the local SQLite file into a cloud Postgres so the site can run
without the machine it grew up on. Deliberately a copy, not a sync: it runs
once, into an empty target, and refuses to guess what to do otherwise.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import Engine, func, insert, select
from sqlmodel import SQLModel

# Importing the models is what puts them in SQLModel.metadata; without this
# the target would be created empty and the copy would find no tables. A model
# missing from this list is copied silently as nothing, so every table the app
# owns has to be named here — test_migrate.py checks that from a clean import.
from app.models.character import Character  # noqa: F401
from app.models.chat import Chat, ChatMessage  # noqa: F401
from app.models.user import User  # noqa: F401

_log = logging.getLogger(__name__)

_BATCH = 500


@dataclass(frozen=True)
class TableResult:
    table: str
    copied: int


class TargetNotEmptyError(RuntimeError):
    """The destination already holds rows, so copying would duplicate them."""


def _tables():
    """Parents before children, so foreign keys resolve as rows land."""
    return SQLModel.metadata.sorted_tables


def count_rows(engine: Engine, table) -> int:
    with engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar_one()


def copy_database(
    source: Engine, target: Engine, *, allow_nonempty: bool = False
) -> list[TableResult]:
    SQLModel.metadata.create_all(target)

    if not allow_nonempty:
        existing = {
            table.name: count_rows(target, table)
            for table in _tables()
            if count_rows(target, table)
        }
        if existing:
            raise TargetNotEmptyError(
                f"В целевой базе уже есть данные: {existing}. "
                "Перенос рассчитан на пустую базу — иначе строки задвоятся."
            )

    results = []
    for table in _tables():
        copied = _copy_table(source, target, table)
        results.append(TableResult(table=table.name, copied=copied))
        _log.info("Copied %d rows into %s", copied, table.name)

    _reset_sequences(target)
    return results


def _copy_table(source: Engine, target: Engine, table) -> int:
    copied = 0
    with source.connect() as read, target.begin() as write:
        rows = read.execute(select(table)).mappings().all()
        for start in range(0, len(rows), _BATCH):
            batch = [dict(row) for row in rows[start : start + _BATCH]]
            if batch:
                write.execute(insert(table), batch)
                copied += len(batch)
    return copied


def _reset_sequences(target: Engine) -> None:
    """Points each Postgres identity sequence past the ids we just inserted.

    Rows are copied with their original ids, which leaves the sequence still
    at 1. Without this the next insert collides on the primary key — and it
    would fail at the user's first save, far from here.
    """
    if target.dialect.name != "postgresql":
        return

    from sqlalchemy import text

    with target.begin() as connection:
        for table in _tables():
            primary = list(table.primary_key.columns)
            if len(primary) != 1 or not primary[0].autoincrement:
                continue
            column = primary[0].name
            connection.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', '{column}'), "
                    f"COALESCE((SELECT MAX({column}) FROM {table.name}), 1))"
                )
            )
