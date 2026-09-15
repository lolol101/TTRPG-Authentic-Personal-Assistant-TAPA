from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class CharacterSnapshot(SQLModel, table=True):
    """A saved copy of a sheet the player can come back to.

    Full copies rather than diffs: a sheet is a few kilobytes of JSON, so
    storing whole ones costs nothing worth counting, and restoring becomes a
    straight write instead of replaying a chain of changes backwards — which
    is the part that goes wrong quietly.

    Saving is deliberate. Nothing snapshots itself, so the list stays a set
    of points the player chose and can recognise.
    """

    id: int | None = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="character.id", index=True)

    name: str = ""
    created_at: datetime = Field(default_factory=_now)

    #: The character's fields at save time, ready to be written back as-is.
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
