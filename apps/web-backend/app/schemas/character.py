from pydantic import BaseModel


class CharacterCreate(BaseModel):
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

    sheet_data: dict = {}


class CharacterUpdate(BaseModel):
    name: str | None = None
    ancestry: str | None = None
    background: str | None = None
    class_name: str | None = None
    level: int | None = None

    str_mod: int | None = None
    dex_mod: int | None = None
    con_mod: int | None = None
    int_mod: int | None = None
    wis_mod: int | None = None
    cha_mod: int | None = None

    hp_max: int | None = None
    hp_current: int | None = None
    ac: int | None = None
    speed: int | None = None

    sheet_data: dict | None = None


class CharacterResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    ancestry: str
    background: str
    class_name: str
    level: int

    str_mod: int
    dex_mod: int
    con_mod: int
    int_mod: int
    wis_mod: int
    cha_mod: int

    hp_max: int
    hp_current: int
    ac: int
    speed: int

    sheet_data: dict
