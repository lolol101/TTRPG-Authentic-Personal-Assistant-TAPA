from __future__ import annotations

import html
import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from langgraph.errors import GraphRecursionError

from bot.session import SessionStore

logger = logging.getLogger(__name__)

router = Router()

AVAILABLE_BOOKS: list[str] = ["pf2e"]


def _make_book_keyboard() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    for book in AVAILABLE_BOOKS:
        kb.button(text=book, callback_data=f"book:{book}")
    kb.adjust(2)
    return kb.as_markup()


# ── commands ──────────────────────────────────────────────────────────────


@router.message(CommandStart())
async def cmd_start(message: Message, session_store: SessionStore) -> None:
    session = session_store.get(message.from_user.id)
    text = (
        "Welcome to **TAPA** — your TTRPG assistant!\n\n"
        "I can help you explore rules, lore, and mechanics from "
        "tabletop RPG books.\n\n"
        "**Commands:**\n"
        "/book — pick a reference book\n"
        "/books — list available books\n"
        "/chat — show current chat mode\n\n"
    )
    if session.book_name:
        text += f"Current book: **{session.book_name}**\n"
    else:
        text += "Use /book to pick a reference book, then just ask a question."
    await message.answer(text)


@router.message(Command("book"))
async def cmd_book(message: Message) -> None:
    await message.answer("Choose a reference book:", reply_markup=_make_book_keyboard())


@router.callback_query(F.data.startswith("book:"))
async def on_book_pick(callback: CallbackQuery, session_store: SessionStore) -> None:
    book = callback.data.split(":", 1)[1]
    session = session_store.get(callback.from_user.id)
    session.book_name = book
    await callback.answer()
    await callback.message.answer(f"Book set to **{book}**. Ask away!")


@router.message(Command("books"))
async def cmd_books(message: Message) -> None:
    lines = ["Available books:"] + [f"  - {b}" for b in AVAILABLE_BOOKS]
    await message.answer("\n".join(lines))


@router.message(Command("chat"))
async def cmd_chat(message: Message) -> None:
    await message.answer("Chat mode is active. Ask your question about the selected book.")


# ── free-text routing ─────────────────────────────────────────────────────


@router.message(F.text)
async def on_text(
    message: Message,
    session_store: SessionStore,
    graph: Any,
) -> None:
    """Route free-text messages through the LangGraph agent."""
    session = session_store.get(message.from_user.id)

    if not session.book_name:
        await message.answer("Please pick a book first with /book")
        return

    await message.chat.do("typing")

    initial_state: dict = {
        "messages": message.text,
        "agents_stack": "primary_agent",
        "book_name": session.book_name,
    }

    last_ai_text: str | None = None

    try:
        for event in graph.stream(
            initial_state,
            stream_mode="values",
        ):
            msgs = event.get("messages")
            if msgs:
                for msg in (msgs if isinstance(msgs, list) else [msgs]):
                    if hasattr(msg, "content") and msg.content:
                        last_ai_text = msg.content
    except GraphRecursionError:
        await message.answer(
            "Request stopped: the agent graph reached its recursion guard. "
            "Please try a more specific instruction."
        )
        return

    logger.debug(
        "on_text: generated_response=%s",
        last_ai_text is not None,
    )

    if last_ai_text:
        for i in range(0, len(last_ai_text), 4000):
            await message.answer(
                html.escape(last_ai_text[i : i + 4000]),
                parse_mode=ParseMode.HTML,
            )
    else:
        await message.answer("Sorry, I could not generate a response.")
