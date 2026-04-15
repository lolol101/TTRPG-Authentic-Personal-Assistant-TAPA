from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UserSession:
    """Mutable per-user state kept in memory for the lifetime of the bot."""

    book_name: str | None = None


class SessionStore:
    """In-memory map from Telegram user-id to session."""

    def __init__(self) -> None:
        self._sessions: dict[int, UserSession] = {}

    def get(self, user_id: int) -> UserSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession()
        return self._sessions[user_id]

    def reset(self, user_id: int) -> None:
        self._sessions.pop(user_id, None)
