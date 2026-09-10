import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.models.character import Character
from app.models.user import User
from app.schemas.ask import AskRequest, AskResponse
from app.services.character_context import build_character_context

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/ping")
def ping() -> dict:
    try:
        response = httpx.get(f"{settings.llm_service_url}/health", timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"llm-service unreachable: {exc}",
        ) from exc

    return response.json()


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    character_context = None
    if payload.character_id is not None:
        character = session.get(Character, payload.character_id)
        if character is None or character.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Character not found"
            )
        character_context = build_character_context(character)

    request_body = payload.model_dump(exclude={"character_id"})
    request_body["character_context"] = character_context

    try:
        response = httpx.post(
            f"{settings.llm_service_url}/ask",
            json=request_body,
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"llm-service unreachable: {exc}",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return response.json()
