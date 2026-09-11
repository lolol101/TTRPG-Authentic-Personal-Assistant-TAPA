from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    k: int | None = None
    """Which game system to answer from; a chosen character decides instead."""
    ruleset: str | None = None
    """Answer for this character; must belong to the requesting user."""
    character_id: int | None = None
    """Continue this chat: its history goes to the model, this turn is saved.

    The chat also settles which character and ruleset apply — it remembers
    that choice, so `character_id` above is ignored when a chat is given.
    """
    chat_id: int | None = None


class Source(BaseModel):
    title: str
    url: str
    source_book: str = ""


class ProposedChange(BaseModel):
    path: str
    value: object = None
    reason: str = ""
    """Human-readable field name and the value this would replace."""
    label: str = ""
    before: object = None


class Memory(BaseModel):
    """How much of the chat the model was shown, so the reader can see where
    its memory ends instead of guessing why an old detail was forgotten."""

    used: int = 0
    dropped: int = 0
    tokens: int = 0
    budget: int = 0


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    """Sheet edits the assistant suggests — applied only once confirmed."""
    proposed_changes: list[ProposedChange] = []
    """Suggestions dropped by validation, with the reason."""
    rejected_changes: list[str] = []
    memory: Memory = Memory()
    """Id of the saved answer, when the question belonged to a chat."""
    message_id: int | None = None
