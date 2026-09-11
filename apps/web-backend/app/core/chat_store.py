"""Reading and writing chats, shared by the chat routes and the ask route.

Both need the same three things — find a chat its owner may touch, read its
history, append a turn — and both need the quotas applied the same way, so
they live here rather than being written twice.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, func, select

from app.core.config import settings
from app.models.chat import Chat, ChatMessage
from app.models.user import User

#: How long a title may run before the list becomes unreadable.
_TITLE_CHARS = 60


class ChatNotFoundError(LookupError):
    """Also raised for someone else's chat: existence is not worth leaking."""


class QuotaExceededError(RuntimeError):
    pass


class MessageTooLongError(ValueError):
    pass


def get_owned_chat(chat_id: int, owner: User, session: Session) -> Chat:
    chat = session.get(Chat, chat_id)
    if chat is None or chat.owner_id != owner.id:
        raise ChatNotFoundError("Chat not found")
    return chat


def message_count(chat_id: int, session: Session) -> int:
    return int(
        session.exec(
            select(func.count()).select_from(ChatMessage).where(ChatMessage.chat_id == chat_id)
        ).one()
    )


def list_messages(chat_id: int, session: Session) -> list[ChatMessage]:
    return list(
        session.exec(
            select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.id)  # type: ignore[arg-type]
        )
    )


def history_for(chat_id: int, session: Session) -> list[dict[str, str]]:
    """The dialogue as llm-service wants it: role and text, oldest first.

    Sources and proposals are deliberately left behind — they are for the
    reader, and re-sending retrieved rule text every turn would fill the
    model's window with the same passages over and over.
    """
    return [
        {"role": message.role, "text": message.text} for message in list_messages(chat_id, session)
    ]


def assert_within_chat_quota(owner: User, session: Session) -> None:
    existing = int(
        session.exec(select(func.count()).select_from(Chat).where(Chat.owner_id == owner.id)).one()
    )
    if existing >= settings.max_chats_per_user:
        raise QuotaExceededError(
            f"Достигнут предел в {settings.max_chats_per_user} чатов. "
            "Удали ненужные, чтобы создать новый."
        )


def assert_within_message_quota(chat_id: int, session: Session) -> None:
    if message_count(chat_id, session) >= settings.max_messages_per_chat:
        raise QuotaExceededError(
            f"В чате уже {settings.max_messages_per_chat} сообщений — это предел. "
            "Начни новый чат, старый никуда не денется."
        )


def assert_message_fits(text: str) -> None:
    if len(text) > settings.max_message_chars:
        raise MessageTooLongError(f"Сообщение длиннее {settings.max_message_chars} символов.")


def title_from(question: str) -> str:
    """Names an untitled chat after the question that started it."""
    first_line = question.strip().splitlines()[0] if question.strip() else ""
    if len(first_line) <= _TITLE_CHARS:
        return first_line
    return first_line[: _TITLE_CHARS - 1].rstrip() + "…"


def add_message(
    chat: Chat,
    session: Session,
    *,
    role: str,
    text: str,
    sources: list | None = None,
    proposed_changes: list | None = None,
    rejected_changes: list | None = None,
) -> ChatMessage:
    """Appends a turn and marks the chat as touched, so lists sort sensibly."""
    message = ChatMessage(
        chat_id=chat.id,
        role=role,
        text=text,
        sources=sources or [],
        proposed_changes=proposed_changes or [],
        rejected_changes=rejected_changes or [],
    )
    session.add(message)

    chat.updated_at = datetime.now(UTC)
    if not chat.title and role == "user":
        chat.title = title_from(text)
    session.add(chat)

    session.commit()
    session.refresh(message)
    return message


def delete_chat(chat: Chat, session: Session) -> None:
    """Messages go with it: nothing else references them, and an orphaned
    message row is invisible in the app but still counts against storage."""
    for message in list_messages(chat.id, session):
        session.delete(message)
    session.delete(chat)
    session.commit()
