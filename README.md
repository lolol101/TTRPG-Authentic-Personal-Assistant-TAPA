# TAPA — TTRPG Authentic Personal Assistant

TAPA — мультиагентный Telegram-бот для настольных ролевых игр.

Он умеет:
- Отвечать на вопросы по правилам и лору из книг (через RAG).
- В будущем сможет редактирвоать файлы связанные с листами персонажей
## Что внутри

```text
[Telegram]
    |
    v
[aiogram]
    |
    v
[LangGraph]
    |
    +--> [Primary (router)] ----+
    |                           |
    `--> [RAG] -----------------+--> [Ollama (LLM)]
              |
              `--> [ChromaDB (vector store)] <--> [e5-large-v2 (embeddings)]
```

Агенты:
- `Primary` — точка входа и маршрутизация, а также основной агент для общения;
- `RAG` — поиск релевантного контекста по книгам.

## Требования

- Python `>=3.12`
- [uv](https://docs.astral.sh/uv/) для управления зависимостями
- [Ollama](https://ollama.com/) с моделью `qwen2.5:7b-instruct`
- Telegram Bot Token от [@BotFather](https://t.me/BotFather)

## Быстрый старт

```bash
git clone <repo-url>
cd TTRPG-Authentic-Personal-Assistant-TAPA
uv sync --extra bot
```

`uv` автоматически создаст локальное окружение `.venv` (если его нет) и установит зависимости.
`--extra bot` включает всё необходимое для запуска бота, включая RAG-часть (эмбеддер + векторное хранилище).
Если нужен полный набор зависимостей (бот + скрапер + dev), используй:

```bash
uv sync --extra all
```

## Настройка `.env`

Создай файл `.env` в корне проекта:

```env
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:7b-instruct

TELEGRAM_BOT_TOKEN=<token_from_botfather>

CHROMA_PERSIST_DIR=./data/vector_db
CHROMA_COLLECTION=books_collection

EMBEDDING_MODEL_ID=intfloat/e5-large-v2

SCRAPER_RATE_LIMIT=1.0
SCRAPER_CACHE_DIR=./data/books_sources

# Optional: LangSmith tracing
LANGSMITH_TRACING=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=TTRPG-Authentic-Personal-Assistant-TAPA
```

## Запуск

```bash
ollama serve

uv run --extra bot python bot/main.py
```

Если при запуске видишь ошибку вида `ModuleNotFoundError: No module named 'torch'`, повторно выполни:

```bash
uv sync --extra bot
```

## Команды бота

| Команда | Назначение |
|---|---|
| `/start` | Приветствие и список команд |
| `/book` | Выбор книги-справочника |
| `/books` | Список доступных книг |
| `/chat` | Возврат в обычный Q&A режим |

## Типовой сценарий

1. Выполни `/book` и выбери книгу.
2. Для вопросов по правилам просто отправляй текст.

## Тесты

```bash
uv run python -m pytest
```

## Структура проекта

```text
agents_core/   # агенты (primary, rag), состояние, промпты
bot/           # Telegram-бот (aiogram): handlers, session, main
config/        # настройки приложения и .env
graph/         # сборка LangGraph
services/      # embedder, vector store, scraper
tests/         # pytest тесты
```
