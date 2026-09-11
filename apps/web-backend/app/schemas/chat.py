from datetime import datetime

from pydantic import BaseModel


class ChatCreate(BaseModel):
    """Title may be empty: the first question names the chat."""

    title: str = ""
    ruleset: str = "pf2e"
    character_id: int | None = None


class ChatUpdate(BaseModel):
    title: str | None = None
    ruleset: str | None = None
    character_id: int | None = None


class ChatResponse(BaseModel):
    id: int
    title: str
    ruleset: str
    character_id: int | None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    text: str
    sources: list = []
    proposed_changes: list = []
    rejected_changes: list = []
    applied: bool = False
    created_at: datetime


class ChatMessageUpdate(BaseModel):
    """Only the applied flag: a message's text is a record, not a draft."""

    applied: bool
