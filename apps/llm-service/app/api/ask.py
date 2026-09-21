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
from app.core.query_rewrite import search_queries_for
from app.core.retriever import retrieve
from app.core.sheet_plan import PlanStep, categories_for, plan_for
from app.core.sse import event
from app.core.tools import CLARIFY_TOOL, SHEET_CHANGE_TOOL
from app.schemas.ask import (
    AskRequest,
    AskResponse,
    Clarification,
    Memory,
    ProposedChange,
    Source,
)

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
        # Asking is offered alongside proposing, and only here: a rules
        # question the model half-understands is cheap to correct, a sheet
        # edited on a guess is not.
        return [SHEET_CHANGE_TOOL, CLARIFY_TOOL]
    return None


def _memory_of(fitted: FittedHistory) -> Memory:
    return Memory(
        used=len(fitted.messages),
        dropped=fitted.dropped,
        tokens=fitted.tokens,
        budget=settings.history_token_budget,
    )


def _collect(retrieved: list[dict], seen: set[str], hits: list[dict]) -> None:
    """Adds what this search found that earlier searches did not.

    A request is now served by several searches — one per area of the sheet,
    or one per phrasing of the question — and they overlap by design. Paying
    context for the same page twice buys nothing.
    """
    for hit in hits:
        key = hit.get("id") or hit["metadata"]["url"]
        if key in seen:
            continue
        seen.add(key)
        retrieved.append(hit)


def _prepare_with_progress(
    payload: AskRequest,
) -> Iterator[str]:
    """Retrieval and prompt assembly, announcing each stage as it starts.

    A split sheet request does a planning call and then one search per area,
    and an ordinary question is rewritten before it is searched — seconds of
    work before a single word of the answer exists. Yielding the stage turns
    that silence into something a reader can follow; the assembled prompt
    comes back as the generator's return value.

    payload.retry_feedback marks a different kind of leg entirely: web-backend
    reporting what its checker did with the model's last proposal, not a new
    question, so nothing here is searched or rewritten for it.
    """
    turns = [Turn(role=message.role, text=message.text) for message in payload.history]
    fitted = fit_history(turns, settings.history_token_budget)

    if payload.retry_feedback is not None:
        # web-backend's checker rejected part of the model's last proposal
        # and is reporting the result, not asking something new — nothing
        # here needs the rulebooks searched again, so no retrieval and no
        # embedding call are made for this leg. See build_ask_messages.
        yield event("stage", {"stage": "revising"})
        messages = build_ask_messages(
            payload.question,
            [],
            payload.character_context,
            allow_sheet_edits=payload.allow_sheet_edits,
            history=fitted.messages,
            retry_feedback=payload.retry_feedback,
        )
        return ([], messages, fitted)

    # A request to change the sheet is really several requests; ask what it
    # touches and search for each part. An ordinary question plans to
    # nothing and keeps the single cheap retrieval it has always had.
    steps: list[PlanStep] = []
    if _tools_for(payload):
        yield event("stage", {"stage": "planning"})
        steps = plan_for(payload.question)

    retrieved: list[dict] = []
    seen: set[str] = set()
    if steps:
        for index, step in enumerate(steps, 1):
            yield event(
                "stage",
                {"stage": "searching", "area": step.area, "index": index, "total": len(steps)},
            )
            # The area is what makes this search different from the others,
            # so it narrows the search as well as wording it: without the
            # filter every area still ranked against the whole corpus, and
            # two thirds of that corpus is feats and equipment.
            categories = categories_for(step.area) if settings.retrieval_filter_by_section else None
            _collect(
                retrieved,
                seen,
                retrieve(step.query, payload.k, ruleset=payload.ruleset, categories=categories),
            )
    else:
        # Searched against the whole history, not the trimmed part: a follow-up
        # should still find the right rule page even when the turn it leans on
        # has already slid out of the model's window.
        query = retrieval_query(payload.question, turns)

        english: list[str] = []
        if settings.retrieval_rewrite_query:
            yield event("stage", {"stage": "rewriting"})
            english = search_queries_for(query)

        yield event("stage", {"stage": "searching"})
        # The English phrasings go first: on this index they are the ones
        # that rank the answering page in the top few, and the model reads
        # the front of its context most closely. One per rule the question
        # names — asked as a single query, a question about two rules is
        # searched for one of them and answered from memory about the other.
        # The question as asked is kept behind them as the safety net for a
        # rewrite that missed.
        for one in english:
            _collect(retrieved, seen, retrieve(one, payload.k, ruleset=payload.ruleset))
        _collect(retrieved, seen, retrieve(query, payload.k, ruleset=payload.ruleset))

    messages = build_ask_messages(
        payload.question,
        retrieved,
        payload.character_context,
        allow_sheet_edits=payload.allow_sheet_edits,
        history=fitted.messages,
    )
    return (retrieved, messages, fitted)


def _prepare(payload: AskRequest) -> tuple[list[dict], list[dict], FittedHistory]:
    """The same work for the non-streaming endpoint, with nobody watching."""
    generator = _prepare_with_progress(payload)
    while True:
        try:
            next(generator)
        except StopIteration as done:
            return done.value


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
        clarification=(
            Clarification(**completion.clarification) if completion.clarification else None
        ),
    )


@router.post("/ask/stream")
def ask_stream(payload: AskRequest) -> StreamingResponse:
    """Same answer as /ask, delivered as it is produced.

    Retrieval finishes long before the model does, so sources go out first:
    the reader gets something real within a moment instead of watching a
    spinner for the whole generation.
    """
    started_at = time.monotonic()
    tools = _tools_for(payload)

    def events() -> Iterator[str]:
        # Prepared inside the generator so planning and each search can be
        # announced as they happen; done before it, the reader would watch
        # a blank screen through the slowest part of the request.
        retrieved, messages, fitted = yield from _prepare_with_progress(payload)

        yield event("sources", [source.model_dump() for source in _sources_of(retrieved)])
        yield event("stage", {"stage": "generating"})

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
                "clarification": completion.clarification if completion else None,
            },
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # Without this an intermediate proxy may buffer the whole response and
        # deliver it at once, which defeats the point.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
