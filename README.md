# TAPA — TTRPG Authentic Personal Assistant

TAPA — ассистент для настольных ролевых игр (сейчас: Pathfinder 2e, открытый
ORC/SRD-контент): советчик по правилам через RAG, редактор листа персонажа и
фундамент для ГМ-планирования партий.

Проект переходит от прежнего Telegram-бота к веб-приложению (backend + frontend)
с отдельным LLM/RAG-сервисом. Актуальный план и статус задач — в
[`docs/BACKLOG.md`](docs/BACKLOG.md), правила разработки — в
[`CLAUDE.md`](CLAUDE.md).

Прежняя черновая реализация (aiogram-бот, LangGraph-роутинг, Chroma) сохранена
в [`legacy/`](legacy/README.md) как референс при переносе логики в новую структуру.

## Структура репозитория

```text
docs/     # BACKLOG.md — источник правды по задачам
legacy/   # черновая реализация (Telegram-бот + RAG) — референс, не эталон
```

Новые сервисы (`apps/web-frontend`, `apps/web-backend`, `apps/llm-service`)
появятся по мере продвижения по бэклогу.
