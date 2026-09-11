from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    k: int | None = None
    """Answer for this character; must belong to the requesting user."""
    character_id: int | None = None


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


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    """Sheet edits the assistant suggests — applied only once confirmed."""
    proposed_changes: list[ProposedChange] = []
    """Suggestions dropped by validation, with the reason."""
    rejected_changes: list[str] = []
