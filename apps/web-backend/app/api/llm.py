import json
from collections.abc import Iterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
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


def _check_proposals(
    character: Character | None, proposals: list[dict]
) -> tuple[list[dict], list[str]]:
    """Filters what the model proposed down to what a sheet edit may touch.

    Nothing is written here either way — the player still confirms.
    """
    if character is None or not proposals:
        return [], []

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
    return [
        {
            "path": change.path,
            "value": change.value,
            "reason": change.reason,
            "label": change.label,
            "before": change.before,
        }
        for change in resolved
    ], rejected


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
    character, character_context = _resolve_character(payload, current_user, session)

    request_body = payload.model_dump(exclude={"character_id"})
    request_body["character_context"] = character_context
    request_body["allow_sheet_edits"] = character is not None
    # A character settles which rules apply; asking Pathfinder questions of a
    # D&D sheet is a mistake the app should not be able to make.
    request_body["ruleset"] = character.ruleset if character else payload.ruleset

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

    proposals = body.pop("proposed_changes", []) or []
    body["proposed_changes"], body["rejected_changes"] = _check_proposals(character, proposals)
    return body


def _resolve_character(
    payload: AskRequest, current_user: User, session: Session
) -> tuple[Character | None, str | None]:
    if payload.character_id is None:
        return None, None

    character = session.get(Character, payload.character_id)
    if character is None or character.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    return character, build_character_context(character)


def _iter_sse_frames(lines: Iterator[str]) -> Iterator[tuple[str, str]]:
    """Reassembles (event, data) pairs from a server-sent event stream."""
    name = ""
    data: list[str] = []
    for line in lines:
        if line.startswith("event:"):
            name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data.append(line[len("data:") :].lstrip())
        elif not line:
            if name or data:
                yield name, "\n".join(data)
            name, data = "", []
    if name or data:
        yield name, "\n".join(data)


@router.post("/ask/stream")
def ask_stream(
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Streams the answer through, vetting sheet proposals at the very end."""
    character, character_context = _resolve_character(payload, current_user, session)

    request_body = payload.model_dump(exclude={"character_id"})
    request_body["character_context"] = character_context
    request_body["allow_sheet_edits"] = character is not None
    # A character settles which rules apply; asking Pathfinder questions of a
    # D&D sheet is a mistake the app should not be able to make.
    request_body["ruleset"] = character.ruleset if character else payload.ruleset

    def events() -> Iterator[str]:
        try:
            with httpx.stream(
                "POST",
                f"{settings.llm_service_url}/ask/stream",
                json=request_body,
                timeout=settings.llm_request_timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    response.read()
                    detail = json.dumps(
                        {"detail": response.text, "status": response.status_code},
                        ensure_ascii=False,
                    )
                    yield f"event: error\ndata: {detail}\n\n"
                    return

                for name, data in _iter_sse_frames(response.iter_lines()):
                    if name != "done":
                        yield f"event: {name}\ndata: {data}\n\n"
                        continue

                    try:
                        finished = json.loads(data)
                    except json.JSONDecodeError:
                        finished = {}
                    proposed, rejected = _check_proposals(
                        character, finished.get("proposed_changes") or []
                    )
                    payload_out = json.dumps(
                        {
                            "proposed_changes": proposed,
                            "rejected_changes": rejected,
                            "provider": finished.get("provider", ""),
                        },
                        ensure_ascii=False,
                    )
                    yield f"event: done\ndata: {payload_out}\n\n"
        except httpx.HTTPError as exc:
            detail = json.dumps(
                {"detail": f"llm-service unreachable: {exc}", "status": 502}, ensure_ascii=False
            )
            yield f"event: error\ndata: {detail}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
