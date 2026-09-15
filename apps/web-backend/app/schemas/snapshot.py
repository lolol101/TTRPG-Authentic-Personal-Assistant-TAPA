from datetime import datetime

from pydantic import BaseModel


class SnapshotCreate(BaseModel):
    """Name may be empty: the save is then labelled with its date and time."""

    name: str = ""


class SnapshotResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
