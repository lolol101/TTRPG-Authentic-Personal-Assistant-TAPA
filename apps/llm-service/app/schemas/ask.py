from typing import Literal

from pydantic import BaseModel


class HistoryMessage(BaseModel):
    """One earlier turn of the same chat, oldest first."""

    role: Literal["user", "assistant"]
    text: str


class AskRequest(BaseModel):
    question: str
    k: int | None = None
    """Which game system to answer from; None searches everything."""
    ruleset: str | None = None
    """Pre-rendered sheet from web-backend; already stripped of user PII."""
    character_context: str | None = None
    """Offer the sheet-editing tool. Only meaningful with a character."""
    allow_sheet_edits: bool = False
    """Earlier turns of this chat. Trimmed here to fit the model's window."""
    history: list[HistoryMessage] = []


class Source(BaseModel):
    title: str
    url: str
    source_book: str = ""


class ProposedChange(BaseModel):
    path: str
    value: object = None
    reason: str = ""


class Memory(BaseModel):
    """How much of the chat the model was actually shown.

    Reported back so the reader can see where its memory ends instead of
    guessing why an old detail was forgotten.
    """

    used: int = 0
    dropped: int = 0
    tokens: int = 0
    budget: int = 0


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    """Suggested sheet edits — nothing is applied until the player confirms."""
    proposed_changes: list[ProposedChange] = []
    memory: Memory = Memory()
