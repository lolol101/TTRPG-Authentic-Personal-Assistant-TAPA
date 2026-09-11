from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class Chat(SQLModel, table=True):
    """One conversation, with the choices it was started under.

    The character and the ruleset belong to the chat rather than to each
    question: a dialogue that switches character halfway would hand the model
    a sheet that contradicts what it said two turns ago. Both can still be
    changed — it is a property of the chat, and changing it is deliberate.
    """

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)

    title: str = ""
    ruleset: str = Field(default="pf2e")
    #: Nullable: a rules question needs no character. Cleared rather than
    #: cascaded when that character is deleted, so the chat survives it.
    character_id: int | None = Field(default=None, foreign_key="character.id", index=True)

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ChatMessage(SQLModel, table=True):
    """One turn. Sources and proposals are kept so a reload looks the same."""

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(foreign_key="chat.id", index=True)

    role: str
    text: str

    sources: list = Field(default_factory=list, sa_column=Column(JSON))
    proposed_changes: list = Field(default_factory=list, sa_column=Column(JSON))
    rejected_changes: list = Field(default_factory=list, sa_column=Column(JSON))
    #: Whether the player accepted the proposed edits, so the button does not
    #: come back offering to apply the same damage twice after a reload.
    applied: bool = False

    created_at: datetime = Field(default_factory=_now)
