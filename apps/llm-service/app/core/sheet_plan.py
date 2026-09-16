"""Splits a sheet-changing request into the areas it touches.

A rules question asks about one thing, and one retrieval serves it. "Build me
a level 1 rogue" asks about six, and the same single retrieval returns five
chunks that cover none of them properly — measured on the real corpus, a
named rule sits at rank 20-50 for a Russian question, so a broad request
retrieves almost nothing it needs and the model fills the gaps from memory.

So: ask what areas the request touches, search for each one separately, and
put the union in front of the model. A request that touches nothing — an
ordinary rules question — is left on the cheap single-retrieval path it has
today, which is the common case and must not pay for this.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.core.llm_provider import Completion, complete
from app.core.tools import PLAN_SHEET_WORK, SHEET_PLAN_TOOL

_log = logging.getLogger(__name__)

#: The parts of a sheet a request can be about, each with the words worth
#: searching when the model names the area but not what to look for. A
#: whitelist: an invented area would spend a retrieval on nothing and put
#: unrelated rules in front of the model.
SHEET_AREAS: dict[str, str] = {
    "ancestry": "происхождение наследие ancestry heritage",
    "background": "предыстория background",
    "class": "класс особенности класса class features",
    "skills": "навыки умения ранги skills proficiency",
    "feats": "черты feats",
    "equipment": "снаряжение оружие доспех equipment weapons armor",
    "spells": "заклинания spells",
    "bio": "биография внешность характер",
}

#: Each step costs a retrieval and lands in one prompt. Past this the context
#: window the retrieval is meant to protect is the thing being blown.
MAX_STEPS = 6


@dataclass(frozen=True)
class PlanStep:
    area: str
    query: str


_PLANNING_INSTRUCTIONS = (
    "Ты планируешь работу с листом персонажа Pathfinder 2e. Тебе дана просьба "
    "игрока. Если она требует изменить лист — назови, какие разделы листа "
    "затронуты, и для каждого дай короткий поисковый запрос по правилам "
    "(лучше по-английски: книги правил на английском). Если это обычный "
    "вопрос по правилам, а не просьба менять лист — не вызывай инструмент "
    "вообще. Не выдумывай разделы: бери только из перечисленных."
)


def _ask_for_plan(question: str) -> Completion:
    return complete(
        [
            {"role": "system", "content": _PLANNING_INSTRUCTIONS},
            {"role": "user", "content": question},
        ],
        tools=[SHEET_PLAN_TOOL],
    )


def _steps_from(raw: str) -> list[PlanStep]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, dict):
        return []

    areas = parsed.get("areas")
    if not isinstance(areas, list):
        return []

    steps: list[PlanStep] = []
    seen: set[str] = set()
    for item in areas:
        if not isinstance(item, dict):
            continue
        area = str(item.get("area") or "").strip().lower()
        if area not in SHEET_AREAS or area in seen:
            continue
        seen.add(area)
        query = str(item.get("query") or "").strip() or SHEET_AREAS[area]
        steps.append(PlanStep(area=area, query=query))
        if len(steps) == MAX_STEPS:
            break
    return steps


def plan_for(question: str) -> list[PlanStep]:
    """The areas this request touches, or [] for an ordinary question.

    Never raises: a planning step that fails must cost the answer nothing,
    and an empty plan is exactly the behaviour the service had before.
    """
    try:
        completion = _ask_for_plan(question)
    except Exception as exc:  # noqa: BLE001 — planning is strictly optional
        _log.warning(
            "sheet planning unavailable (%s); answering the simple way", type(exc).__name__
        )
        return []

    raw = completion.tool_arguments.get(PLAN_SHEET_WORK)
    if not raw:
        return []

    steps = _steps_from(raw)
    if steps:
        _log.info(
            "sheet request split into %d areas: %s",
            len(steps),
            ", ".join(step.area for step in steps),
        )
    return steps


__all__ = ["MAX_STEPS", "PLAN_SHEET_WORK", "SHEET_AREAS", "PlanStep", "plan_for"]
