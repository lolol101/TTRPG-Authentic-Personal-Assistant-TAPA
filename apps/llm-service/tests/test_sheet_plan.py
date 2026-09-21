"""Splitting a sheet-filling request into the areas it actually touches.

One retrieval cannot serve "build me a level 1 rogue": k=5 over 13494 chunks
returns five chunks that between them cover neither the ancestry, nor the
class feats, nor the equipment. Measured on the real corpus, a named rule
lands at rank 20-50 for a Russian question — so a broad request retrieves
almost nothing it needs. Asking per area is what makes the context match the
question.
"""

import json

import pytest

from app.core import sheet_plan
from app.core.llm_provider import Completion
from app.core.tools import PLAN_SHEET_WORK


def _planning_completion(areas: list[dict]) -> Completion:
    return Completion(
        text="",
        proposed_changes=[],
        provider="test",
        tool_arguments={PLAN_SHEET_WORK: json.dumps({"areas": areas})},
    )


def test_a_simple_question_is_not_decomposed(monkeypatch) -> None:
    """The whole point of the split is broad sheet edits; a rules question
    must keep the single cheap retrieval it has today."""
    monkeypatch.setattr(sheet_plan, "_ask_for_plan", lambda question: _planning_completion([]))

    assert sheet_plan.plan_for("Что делает действие Grapple?") == []


def test_a_fill_the_sheet_request_is_split_into_areas(monkeypatch) -> None:
    monkeypatch.setattr(
        sheet_plan,
        "_ask_for_plan",
        lambda question: _planning_completion(
            [
                {"area": "ancestry", "query": "elf ancestry heritage level 1"},
                {"area": "class", "query": "rogue class features level 1"},
                {"area": "equipment", "query": "rogue starting equipment"},
            ]
        ),
    )

    plan = sheet_plan.plan_for("Собери плута 1 уровня целиком")

    assert [step.area for step in plan] == ["ancestry", "class", "equipment"]
    assert plan[0].query == "elf ancestry heritage level 1"


def test_an_unknown_area_is_dropped_rather_than_searched(monkeypatch) -> None:
    """The area list is a whitelist: a made-up area would spend a retrieval
    on nothing and put unrelated rules in front of the model."""
    monkeypatch.setattr(
        sheet_plan,
        "_ask_for_plan",
        lambda question: _planning_completion(
            [
                {"area": "spaceship", "query": "warp drive"},
                {"area": "equipment", "query": "rogue gear"},
            ]
        ),
    )

    plan = sheet_plan.plan_for("Собери плута")

    assert [step.area for step in plan] == ["equipment"]


def test_a_step_without_a_query_falls_back_to_the_area_itself(monkeypatch) -> None:
    monkeypatch.setattr(
        sheet_plan,
        "_ask_for_plan",
        lambda question: _planning_completion([{"area": "skills", "query": "  "}]),
    )

    plan = sheet_plan.plan_for("Собери плута")

    assert len(plan) == 1
    assert plan[0].query, "an empty query would retrieve noise"


def test_the_plan_is_capped(monkeypatch) -> None:
    """Every area costs a retrieval and lands in one prompt; an unbounded
    plan would blow the context window the retrieval is meant to protect."""
    monkeypatch.setattr(
        sheet_plan,
        "_ask_for_plan",
        lambda question: _planning_completion(
            [{"area": area, "query": area} for area in sheet_plan.SHEET_AREAS] * 3
        ),
    )

    plan = sheet_plan.plan_for("Собери плута")

    assert len(plan) <= sheet_plan.MAX_STEPS


def test_the_same_area_is_not_searched_twice(monkeypatch) -> None:
    monkeypatch.setattr(
        sheet_plan,
        "_ask_for_plan",
        lambda question: _planning_completion(
            [
                {"area": "equipment", "query": "armour"},
                {"area": "equipment", "query": "weapons"},
            ]
        ),
    )

    assert len(sheet_plan.plan_for("Собери плута")) == 1


@pytest.mark.parametrize("broken", ["not json at all", "[]", '{"areas": "nope"}', ""])
def test_an_unreadable_plan_degrades_to_the_simple_path(monkeypatch, broken) -> None:
    """A planning step that fails must cost the answer nothing: the request
    falls back to exactly the retrieval it would have had before."""
    monkeypatch.setattr(
        sheet_plan,
        "_ask_for_plan",
        lambda question: Completion(
            text="", provider="test", tool_arguments={PLAN_SHEET_WORK: broken}
        ),
    )

    assert sheet_plan.plan_for("Собери плута") == []


def test_a_provider_failure_degrades_to_the_simple_path(monkeypatch) -> None:
    def _boom(question):
        raise RuntimeError("provider down")

    monkeypatch.setattr(sheet_plan, "_ask_for_plan", _boom)

    assert sheet_plan.plan_for("Собери плута") == []


def test_every_mapped_area_is_a_real_sheet_area() -> None:
    """The two tables sit next to each other and must not drift: a category
    mapped for an area the planner cannot name would never be used."""
    assert set(sheet_plan.AREA_CATEGORIES) <= set(sheet_plan.SHEET_AREAS)


def test_categories_for_names_the_sections_that_answer_an_area() -> None:
    assert sheet_plan.categories_for("class") == ("classes", "class-features")
    assert sheet_plan.categories_for("background") == ("backgrounds",)


def test_skills_is_deliberately_unmapped() -> None:
    """No category holds the rules chapters about trained/expert ranks —
    measured, filtering "skills proficiency trained rank" moved 0 of 5
    on-section hits to 0 of 5. So it searches everything, as before."""
    assert sheet_plan.categories_for("skills") is None
    assert "skills" in sheet_plan.SHEET_AREAS


def test_bio_is_unmapped_because_it_needs_no_rules() -> None:
    assert sheet_plan.categories_for("bio") is None


def test_an_area_the_planner_invented_restricts_nothing() -> None:
    assert sheet_plan.categories_for("nonsense") is None
