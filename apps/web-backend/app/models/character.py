from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Character(SQLModel, table=True):
    """A character sheet belonging to one ruleset.

    Every game system has its own sheet, so `sheet_data` holds whatever that
    system needs and `ruleset` says how to read it. The typed columns are the
    small set common enough to query directly and shared across systems —
    name, level, hit points, a defense number.
    """

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    ruleset: str = Field(default="pf2e", index=True)

    name: str
    ancestry: str = ""
    background: str = ""
    class_name: str = ""
    level: int = 1

    str_mod: int = 0
    dex_mod: int = 0
    con_mod: int = 0
    int_mod: int = 0
    wis_mod: int = 0
    cha_mod: int = 0

    hp_max: int = 0
    hp_current: int = 0
    ac: int = 10
    speed: int = 25

    sheet_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
