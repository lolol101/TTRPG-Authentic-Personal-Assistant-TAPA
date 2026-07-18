from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from langchain_openai import ChatOpenAI

from bot.handlers import router
from bot.session import SessionStore
from config.settings import settings
from graph.builder import build_graph
from services.vector_store import create_vector_store

_log = logging.getLogger(__name__)


def _create_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.ollama_model,
        api_key="ollama",
        base_url=settings.ollama_base_url,
        temperature=0.7,
        max_tokens=1024,
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logging.getLogger("bot.handlers").setLevel(logging.DEBUG)

    _log.info("Initializing LLM and vector store...")
    llm = _create_llm()
    try:
        vector_db = create_vector_store()
    except Exception as exc:
        _log.critical(
            "Failed to load embedding model — RAG will not work.\n"
            "Install bot dependencies: uv sync --extra bot\nError: %s",
            exc,
            exc_info=True,
        )
        raise SystemExit(1) from exc

    graph = build_graph(llm, vector_db, book_name="pf2e")
    session_store = SessionStore()

    dp = Dispatcher()
    dp["session_store"] = session_store
    dp["graph"] = graph
    dp.include_router(router)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    _log.info("Bot is starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
