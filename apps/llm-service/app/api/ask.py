from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, status
from openai import OpenAIError

from app.core.llm_provider import LLMNotConfiguredError, complete
from app.core.prompts import build_ask_prompt
from app.core.retriever import retrieve
from app.core.tools import SHEET_CHANGE_TOOL
from app.schemas.ask import AskRequest, AskResponse, ProposedChange, Source

router = APIRouter(tags=["ask"])
_log = logging.getLogger(__name__)


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    started_at = time.monotonic()
    retrieved = retrieve(payload.question, payload.k)
    prompt = build_ask_prompt(
        payload.question,
        retrieved,
        payload.character_context,
        allow_sheet_edits=payload.allow_sheet_edits,
    )

    # The tool is only offered when a sheet is actually in play; without one
    # there is nothing for the model to propose changes against.
    tools = [SHEET_CHANGE_TOOL] if payload.allow_sheet_edits and payload.character_context else None

    try:
        completion = complete(prompt, tools=tools)
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
        "ask: question=%r k=%s with_character=%s tools=%s proposals=%s sources=%s elapsed_ms=%.0f",
        payload.question,
        payload.k,
        payload.character_context is not None,
        bool(tools),
        len(completion.proposed_changes),
        [r["metadata"]["title"] for r in retrieved],
        elapsed_ms,
    )

    sources = [
        Source(
            title=r["metadata"]["title"],
            url=r["metadata"]["url"],
            source_book=r["metadata"].get("source_book", ""),
        )
        for r in retrieved
    ]
    return AskResponse(
        answer=completion.text,
        sources=sources,
        proposed_changes=[ProposedChange(**change) for change in completion.proposed_changes],
    )
