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


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
