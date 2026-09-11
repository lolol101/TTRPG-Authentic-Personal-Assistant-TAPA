from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.chat_store import (
    ChatNotFoundError,
    QuotaExceededError,
    assert_within_chat_quota,
    delete_chat,
    get_owned_chat,
    list_messages,
    message_count,
)
from app.core.db import get_session
from app.models.character import Character
from app.models.chat import Chat, ChatMessage
from app.models.user import User
from app.schemas.chat import (
    ChatCreate,
    ChatMessageResponse,
    ChatMessageUpdate,
    ChatResponse,
    ChatUpdate,
)

router = APIRouter(prefix="/chats", tags=["chats"])


def _owned_chat(chat_id: int, owner: User, session: Session) -> Chat:
    try:
        return get_owned_chat(chat_id, owner, session)
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _check_character(character_id: int | None, owner: User, session: Session) -> None:
    """A chat may only point at a character its owner actually has."""
    if character_id is None:
        return
    character = session.get(Character, character_id)
    if character is None or character.owner_id != owner.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")


def _to_response(chat: Chat, session: Session) -> ChatResponse:
    return ChatResponse(
        id=chat.id,
        title=chat.title,
        ruleset=chat.ruleset,
        character_id=chat.character_id,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=message_count(chat.id, session),
    )


@router.get("", response_model=list[ChatResponse])
def list_chats(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ChatResponse]:
    """Most recently used first — that is the one being continued."""
    chats = session.exec(
        select(Chat).where(Chat.owner_id == current_user.id).order_by(Chat.updated_at.desc())  # type: ignore[attr-defined]
    )
    return [_to_response(chat, session) for chat in chats]


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
    payload: ChatCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ChatResponse:
    try:
        assert_within_chat_quota(current_user, session)
    except QuotaExceededError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    _check_character(payload.character_id, current_user, session)

    chat = Chat(owner_id=current_user.id, **payload.model_dump())
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return _to_response(chat, session)


@router.get("/{chat_id}", response_model=ChatResponse)
def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ChatResponse:
    return _to_response(_owned_chat(chat_id, current_user, session), session)


@router.patch("/{chat_id}", response_model=ChatResponse)
def update_chat(
    chat_id: int,
    payload: ChatUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ChatResponse:
    chat = _owned_chat(chat_id, current_user, session)
    fields = payload.model_dump(exclude_unset=True)

    if "character_id" in fields:
        _check_character(fields["character_id"], current_user, session)

    for field, value in fields.items():
        setattr(chat, field, value)

    # The list is ordered by this, and a rename is a use of the chat.
    chat.updated_at = datetime.now(UTC)
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return _to_response(chat, session)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    delete_chat(_owned_chat(chat_id, current_user, session), session)


@router.get("/{chat_id}/messages", response_model=list[ChatMessageResponse])
def get_messages(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ChatMessage]:
    chat = _owned_chat(chat_id, current_user, session)
    return list_messages(chat.id, session)


@router.patch("/{chat_id}/messages/{message_id}", response_model=ChatMessageResponse)
def update_message(
    chat_id: int,
    message_id: int,
    payload: ChatMessageUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ChatMessage:
    """Records that the player accepted the proposed edits.

    Without it a reload would offer to apply the same damage a second time.
    """
    chat = _owned_chat(chat_id, current_user, session)
    message = session.get(ChatMessage, message_id)
    if message is None or message.chat_id != chat.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    message.applied = payload.applied
    session.add(message)
    session.commit()
    session.refresh(message)
    return message
