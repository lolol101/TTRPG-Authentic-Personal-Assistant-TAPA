from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Character(SQLModel, table=True):
    """A PF2e character sheet.

    Core identity/combat fields are typed columns; less-structured parts of
    the sheet (skills, feats, inventory) live in `sheet_data` as JSON. This
    avoids modeling the entire PF2e sheet relationally up front — the
    typed columns can grow as specific features (e.g. skill checks) need
    to query into them directly.
    """

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)

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
