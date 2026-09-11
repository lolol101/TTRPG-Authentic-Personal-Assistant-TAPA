import json
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.chat_store import (
    ChatNotFoundError,
    MessageTooLongError,
    QuotaExceededError,
    add_message,
    assert_message_fits,
    assert_within_message_quota,
    get_owned_chat,
    history_for,
)
from app.core.config import settings
from app.core.db import get_session
from app.models.character import Character
from app.models.chat import Chat
from app.models.user import User
from app.rulesets.pf2e.context import build_character_context
from app.rulesets.pf2e.edits import ProposedChange, resolve_changes
from app.schemas.ask import AskRequest, AskResponse

router = APIRouter(prefix="/llm", tags=["llm"])


@dataclass
class _Conversation:
    """Everything the question needs to know about where it was asked."""

    chat: Chat | None = None
    character: Character | None = None
    character_context: str | None = None
    history: list[dict[str, str]] = field(default_factory=list)


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


def _resolve_character(
    character_id: int | None, current_user: User, session: Session
) -> tuple[Character | None, str | None]:
    if character_id is None:
        return None, None

    character = session.get(Character, character_id)
    if character is None or character.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    return character, build_character_context(character)


def _open_conversation(payload: AskRequest, current_user: User, session: Session) -> _Conversation:
    """Loads the chat, its history and its character, and applies the quotas.

    The history is read before this question is stored anywhere, so the model
    is never handed the same question twice.
    """
    try:
        assert_message_fits(payload.question)
    except MessageTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc

    if payload.chat_id is None:
        character, context = _resolve_character(payload.character_id, current_user, session)
        return _Conversation(character=character, character_context=context)

    try:
        chat = get_owned_chat(payload.chat_id, current_user, session)
        assert_within_message_quota(chat.id, session)
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except QuotaExceededError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    # The chat holds the choice, so a dialogue cannot switch character
    # halfway and leave the model contradicting what it said two turns ago.
    character, context = _resolve_character(chat.character_id, current_user, session)
    return _Conversation(
        chat=chat,
        character=character,
        character_context=context,
        history=history_for(chat.id, session),
    )


def _request_body(payload: AskRequest, conversation: _Conversation) -> dict:
    body = payload.model_dump(exclude={"character_id", "chat_id"})
    body["character_context"] = conversation.character_context
    body["allow_sheet_edits"] = conversation.character is not None
    # A character settles which rules apply; asking Pathfinder questions of a
    # D&D sheet is a mistake the app should not be able to make.
    if conversation.character:
        body["ruleset"] = conversation.character.ruleset
    elif conversation.chat:
        body["ruleset"] = conversation.chat.ruleset
    body["history"] = conversation.history
    return body


def _save_turn(
    conversation: _Conversation,
    session: Session,
    *,
    question: str,
    answer: str,
    sources: list,
    proposed: list,
    rejected: list,
) -> int | None:
    """Stores the question and its answer together, once the answer exists.

    Saving the question up front would strand it in the history whenever the
    provider fails, and the retry would then ask it a second time.
    """
    if conversation.chat is None:
        return None

    add_message(conversation.chat, session, role="user", text=question)
    saved = add_message(
        conversation.chat,
        session,
        role="assistant",
        text=answer,
        sources=sources,
        proposed_changes=proposed,
        rejected_changes=rejected,
    )
    return saved.id


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    conversation = _open_conversation(payload, current_user, session)

    try:
        response = httpx.post(
            f"{settings.llm_service_url}/ask",
            json=_request_body(payload, conversation),
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
    body["proposed_changes"], body["rejected_changes"] = _check_proposals(
        conversation.character, proposals
    )
    body["message_id"] = _save_turn(
        conversation,
        session,
        question=payload.question,
        answer=body.get("answer", ""),
        sources=body.get("sources", []),
        proposed=body["proposed_changes"],
        rejected=body["rejected_changes"],
    )
    return body


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
    conversation = _open_conversation(payload, current_user, session)
    request_body = _request_body(payload, conversation)

    def events() -> Iterator[str]:
        # Collected as it flows past so the finished turn can be stored: the
        # stream is the only place the whole answer ever exists.
        answer: list[str] = []
        sources: list = []

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
                    if name == "sources":
                        sources = json.loads(data)
                    elif name == "delta":
                        answer.append(json.loads(data).get("text", ""))

                    if name != "done":
                        yield f"event: {name}\ndata: {data}\n\n"
                        continue

                    try:
                        finished = json.loads(data)
                    except json.JSONDecodeError:
                        finished = {}
                    proposed, rejected = _check_proposals(
                        conversation.character, finished.get("proposed_changes") or []
                    )
                    message_id = _save_turn(
                        conversation,
                        session,
                        question=payload.question,
                        answer="".join(answer),
                        sources=sources,
                        proposed=proposed,
                        rejected=rejected,
                    )
                    payload_out = json.dumps(
                        {
                            "proposed_changes": proposed,
                            "rejected_changes": rejected,
                            "provider": finished.get("provider", ""),
                            "memory": finished.get("memory", {}),
                            "message_id": message_id,
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
