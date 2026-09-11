import pytest
from sqlalchemy import func, select
from sqlmodel import Session, SQLModel, create_engine

from app.core.migrate import TargetNotEmptyError, copy_database
from app.models.character import Character
from app.models.user import User


@pytest.fixture(name="source")
def source_fixture(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'source.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=1, email="alice@example.com", password_hash="hash-a"))
        session.add(User(id=2, email="bob@example.com", password_hash="hash-b"))
        session.add(Character(id=7, owner_id=1, name="Рэм Байер", level=5, hp_current=60))
        session.add(Character(id=8, owner_id=2, name="Seelah", level=3, sheet_data={"xp": 400}))
        session.commit()
    return engine


@pytest.fixture(name="target")
def target_fixture(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'target.db'}")


def _count(engine, model) -> int:
    with Session(engine) as session:
        return session.exec(select(func.count()).select_from(model)).one()[0]


def test_copies_every_table(source, target) -> None:
    results = copy_database(source, target)

    assert {result.table: result.copied for result in results} == {"user": 2, "character": 2}
    assert _count(target, User) == 2
    assert _count(target, Character) == 2


def test_keeps_ids_so_characters_still_belong_to_their_owner(source, target) -> None:
    copy_database(source, target)

    with Session(target) as session:
        character = session.get(Character, 7)
        assert character.name == "Рэм Байер"
        assert character.owner_id == 1
        assert session.get(User, 1).email == "alice@example.com"


def test_carries_the_json_half_of_the_sheet(source, target) -> None:
    copy_database(source, target)

    with Session(target) as session:
        assert session.get(Character, 8).sheet_data == {"xp": 400}


def test_refuses_a_target_that_already_holds_rows(source, target) -> None:
    copy_database(source, target)

    # Running it twice must not silently double every character.
    with pytest.raises(TargetNotEmptyError, match="задвоятся"):
        copy_database(source, target)


def test_an_empty_source_copies_cleanly(tmp_path, target) -> None:
    empty = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    SQLModel.metadata.create_all(empty)

    results = copy_database(empty, target)

    assert all(result.copied == 0 for result in results)


def test_password_is_never_printed_when_reporting_the_destination() -> None:
    """The destination URL is echoed to the console; the password is not."""
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "scripts" / "migrate_to_postgres.py"
    spec = importlib.util.spec_from_file_location("migrate_script", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    shown = module._redact("postgresql+psycopg://user:s3cret@host/db?sslmode=require")

    assert "s3cret" not in shown
    assert shown.startswith("postgresql+psycopg://user:***@host")
