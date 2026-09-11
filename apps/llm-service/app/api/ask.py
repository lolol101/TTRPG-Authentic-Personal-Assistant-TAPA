from __future__ import annotations

import logging
import time
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from openai import OpenAIError

from app.core.config import settings
from app.core.history import FittedHistory, Turn, fit_history, retrieval_query
from app.core.llm_provider import Completion, LLMNotConfiguredError, complete, stream
from app.core.prompts import build_ask_messages
from app.core.retriever import retrieve
from app.core.sse import event
from app.core.tools import SHEET_CHANGE_TOOL
from app.schemas.ask import AskRequest, AskResponse, Memory, ProposedChange, Source

router = APIRouter(tags=["ask"])
_log = logging.getLogger(__name__)


def _sources_of(retrieved: list[dict]) -> list[Source]:
    return [
        Source(
            title=r["metadata"]["title"],
            url=r["metadata"]["url"],
            source_book=r["metadata"].get("source_book", ""),
        )
        for r in retrieved
    ]


def _tools_for(payload: AskRequest) -> list[dict] | None:
    # The tool is only offered when a sheet is actually in play; without one
    # there is nothing for the model to propose changes against.
    if payload.allow_sheet_edits and payload.character_context:
        return [SHEET_CHANGE_TOOL]
    return None


def _memory_of(fitted: FittedHistory) -> Memory:
    return Memory(
        used=len(fitted.messages),
        dropped=fitted.dropped,
        tokens=fitted.tokens,
        budget=settings.history_token_budget,
    )


def _prepare(payload: AskRequest) -> tuple[list[dict], list[dict], FittedHistory]:
    """Retrieval and prompt assembly, shared by the two endpoints."""
    turns = [Turn(role=message.role, text=message.text) for message in payload.history]
    fitted = fit_history(turns, settings.history_token_budget)

    # Searched against the whole history, not the trimmed part: a follow-up
    # should still find the right rule page even when the turn it leans on
    # has already slid out of the model's window.
    retrieved = retrieve(
        retrieval_query(payload.question, turns), payload.k, ruleset=payload.ruleset
    )

    messages = build_ask_messages(
        payload.question,
        retrieved,
        payload.character_context,
        allow_sheet_edits=payload.allow_sheet_edits,
        history=fitted.messages,
    )
    return retrieved, messages, fitted


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    started_at = time.monotonic()
    retrieved, messages, fitted = _prepare(payload)
    tools = _tools_for(payload)

    try:
        completion = complete(messages, tools=tools)
    except LLMNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except OpenAIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM provider error: {exc}",
        ) from exc

    elapsed_ms = (time.monotonic() - started_at) * 1000
    _log.info(
        "ask: question=%r k=%s with_character=%s tools=%s history=%s/%s proposals=%s "
        "sources=%s elapsed_ms=%.0f",
        payload.question,
        payload.k,
        payload.character_context is not None,
        bool(tools),
        len(fitted.messages),
        len(payload.history),
        len(completion.proposed_changes),
        [r["metadata"]["title"] for r in retrieved],
        elapsed_ms,
    )

    return AskResponse(
        answer=completion.text,
        sources=_sources_of(retrieved),
        proposed_changes=[ProposedChange(**change) for change in completion.proposed_changes],
        memory=_memory_of(fitted),
    )


@router.post("/ask/stream")
def ask_stream(payload: AskRequest) -> StreamingResponse:
    """Same answer as /ask, delivered as it is produced.

    Retrieval finishes long before the model does, so sources go out first:
    the reader gets something real within a moment instead of watching a
    spinner for the whole generation.
    """
    started_at = time.monotonic()
    retrieved, messages, fitted = _prepare(payload)
    tools = _tools_for(payload)

    def events() -> Iterator[str]:
        yield event("sources", [source.model_dump() for source in _sources_of(retrieved)])

        completion: Completion | None = None
        try:
            for item in stream(messages, tools=tools):
                if isinstance(item, Completion):
                    completion = item
                else:
                    yield event("delta", {"text": item})
        except LLMNotConfiguredError as exc:
            yield event("error", {"detail": str(exc), "status": 503})
            return
        except OpenAIError as exc:
            # The stream has already begun, so the HTTP status is long since
            # sent — the failure has to travel as an event instead.
            yield event("error", {"detail": f"LLM provider error: {exc}", "status": 502})
            return

        elapsed_ms = (time.monotonic() - started_at) * 1000
        _log.info(
            "ask/stream: question=%r k=%s with_character=%s tools=%s history=%s/%s "
            "proposals=%s sources=%s elapsed_ms=%.0f",
            payload.question,
            payload.k,
            payload.character_context is not None,
            bool(tools),
            len(fitted.messages),
            len(payload.history),
            len(completion.proposed_changes) if completion else 0,
            [r["metadata"]["title"] for r in retrieved],
            elapsed_ms,
        )

        yield event(
            "done",
            {
                "proposed_changes": completion.proposed_changes if completion else [],
                "provider": completion.provider if completion else "",
                "memory": _memory_of(fitted).model_dump(),
            },
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # Without this an intermediate proxy may buffer the whole response and
        # deliver it at once, which defeats the point.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
