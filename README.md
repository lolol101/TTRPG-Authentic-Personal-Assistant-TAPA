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
apps/
  web-frontend/   # React + TS (Vite)
  web-backend/    # FastAPI: аутентификация, персонажи, прокси к llm-service
  llm-service/    # FastAPI: RAG/LLM (пока только /health)
docs/             # BACKLOG.md — источник правды по задачам
legacy/           # черновая реализация (Telegram-бот + RAG) — референс, не эталон
```

Каждый сервис в `apps/` — независимый проект (свой `pyproject.toml`/venv или
`package.json`), не общий монорепо-workspace.

## Запуск сквозного скелета

### bash / zsh

```bash
# терминал 1 — llm-service (порт 8100)
cd apps/llm-service && uv sync && uv run uvicorn app.main:app --port 8100

# терминал 2 — web-backend (порт 8000)
cd apps/web-backend && uv sync && uv run uvicorn app.main:app --port 8000

# терминал 3 — web-frontend (порт 5173, проксирует /auth, /health, /llm на :8000)
cd apps/web-frontend && npm install && npm run dev
```

### PowerShell

```powershell
# терминал 1 — llm-service (порт 8100)
Set-Location apps/llm-service
uv sync
uv run uvicorn app.main:app --port 8100

# терминал 2 — web-backend (порт 8000)
Set-Location apps/web-backend
uv sync
uv run uvicorn app.main:app --port 8000

# терминал 3 — web-frontend (порт 5173, проксирует /auth, /health, /llm на :8000)
Set-Location apps/web-frontend
npm install
npm run dev
```

Открыть `http://localhost:5173/` — регистрация/вход, вкладка «Персонажи»
(лист персонажа PF2e по образцу Roll20) и вкладка «Правила» (вопрос по
проиндексированным правилам через RAG).

Фронтенд использует `shadcn/ui` + Tailwind v4; компоненты лежат в
`apps/web-frontend/src/components/ui` и правятся как обычный код репозитория.

> Дев-сервер и его прокси намеренно прибиты к `127.0.0.1`: по умолчанию Vite
> слушает только `::1`, а Node резолвит `localhost` в `::1` раньше `127.0.0.1` —
> при этом uvicorn слушает IPv4. В такой связке прокси молча отдавал `index.html`
> вместо ответа бэкенда, и формы входа/вопроса не работали.
