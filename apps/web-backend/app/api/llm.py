import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.models.character import Character
from app.models.user import User
from app.rulesets.pf2e.context import build_character_context
from app.rulesets.pf2e.edits import ProposedChange, resolve_changes
from app.schemas.ask import AskRequest, AskResponse

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
    character = None
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
    request_body["allow_sheet_edits"] = character is not None

    try:
        response = httpx.post(
            f"{settings.llm_service_url}/ask",
            json=request_body,
            timeout=settings.llm_request_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"llm-service unreachable: {exc}",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    body = response.json()

    # Whatever the model proposed is checked here against what a sheet edit
    # may touch at all. Nothing is written: the player confirms first.
    proposals = body.pop("proposed_changes", []) or []
    if character is not None and proposals:
        resolved, rejected = resolve_changes(
            character,
            [
                ProposedChange(
                    path=str(item.get("path", "")),
                    value=item.get("value"),
                    reason=str(item.get("reason") or ""),
                )
                for item in proposals
            ],
        )
        body["proposed_changes"] = [
            {
                "path": change.path,
                "value": change.value,
                "reason": change.reason,
                "label": change.label,
                "before": change.before,
            }
            for change in resolved
        ]
        body["rejected_changes"] = rejected
    else:
        body["proposed_changes"] = []
        body["rejected_changes"] = []

    return body
