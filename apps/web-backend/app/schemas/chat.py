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
    """Only what became of the proposals: the text is a record, not a draft."""

    applied: bool
    #: Which paths the player just applied. Sent per section as they are
    #: applied, while `applied` stays false until nothing is left — the flag
    #: answers "may this turn still be applied", these answer "what was
    #: taken", and a partly applied turn needs both.
    applied_paths: list[str] = []
