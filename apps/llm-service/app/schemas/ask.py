from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    k: int | None = None


class Source(BaseModel):
    title: str
    url: str
    source_book: str = ""


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
