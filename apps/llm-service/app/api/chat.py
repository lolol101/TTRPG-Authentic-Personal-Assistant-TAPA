import openai
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core import llm_provider

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        reply = llm_provider.complete(payload.message)
    except openai.APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM provider unreachable: {exc}",
        ) from exc

    return ChatResponse(reply=reply)
