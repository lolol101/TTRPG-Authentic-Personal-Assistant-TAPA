from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    k: int | None = None
    """Pre-rendered sheet from web-backend; already stripped of user PII."""
    character_context: str | None = None
    """Offer the sheet-editing tool. Only meaningful with a character."""
    allow_sheet_edits: bool = False


class Source(BaseModel):
    title: str
    url: str
    source_book: str = ""


class ProposedChange(BaseModel):
    path: str
    value: object = None
    reason: str = ""


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    """Suggested sheet edits — nothing is applied until the player confirms."""
    proposed_changes: list[ProposedChange] = []
