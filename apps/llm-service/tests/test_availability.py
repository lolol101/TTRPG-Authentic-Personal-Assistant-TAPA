"""What a found page requires of a character's level, worked out in code.

Replayed live chat: the model put Slow "at level 3" and Stagnate Time "at
level 5" for a wizard — from memory, and wrong both times (rank N opens at
level 2N-1). A note computed here travels with each page instead, so the
model reads the number rather than producing it.
"""

import pytest

from app.rulesets import availability_note


def _page(header: str, traits: str = "", ruleset: str = "pf2e", title: str = "X") -> dict:
    return {
        "id": title,
        "text": f"{title}\n\n{header}\n\nDescription text.",
        "metadata": {"title": title, "ruleset": ruleset, "traits": traits},
    }


@pytest.mark.parametrize(
    ("rank", "level"),
    [(1, 1), (2, 3), (3, 5), (5, 9), (10, 19)],
)
def test_a_spell_rank_opens_at_level_2n_minus_1(rank, level) -> None:
    note = availability_note(_page(f"Spell {rank} · Traits: concentrate"), None)

    assert f"{rank}-го круга" in note
    assert f"на {level}-м уровне" in note


def test_a_spell_above_the_characters_reach_is_marked_not_yet_open() -> None:
    note = availability_note(_page("Spell 3 · Traits: concentrate, manipulate"), 1)

    assert "ещё не открыт" in note
    assert "1-й уровень" in note


def test_a_spell_within_reach_is_marked_open() -> None:
    assert "уже открыт" in availability_note(_page("Spell 3 · Traits: concentrate"), 5)


def test_a_cantrip_is_not_limited_by_level() -> None:
    """Foundry files cantrips as "Spell 1" with a cantrip trait; read as a
    1st-rank spell, every level comparison on it would be meaningless."""
    note = availability_note(_page("Spell 1 · Traits: cantrip, force", "cantrip, force"), 1)

    assert "заговор" in note
    assert "круга" not in note


def test_a_focus_spell_says_its_access_is_not_about_rank() -> None:
    note = availability_note(_page("Spell 1 · Traits: focus, wizard", "focus, wizard"), 1)

    assert "фокус" in note
    assert "круга" not in note


def test_a_feat_is_taken_from_its_own_level() -> None:
    note = availability_note(_page("Feat 8 · Traits: archetype · Category class"), 4)

    assert "8-го уровня" in note
    assert "ещё не открыт" in note


@pytest.mark.parametrize("kind", ["Weapon", "Armor", "Shield", "Equipment", "Consumable"])
def test_an_item_states_its_level_against_the_characters(kind) -> None:
    """Only the comparison — how an item may be bought is a rule the page
    has to state, not one this note may imply."""
    note = availability_note(_page(f"{kind} 3 · Price 60 gp"), 1)

    assert "3-го уровня" in note
    assert "выше уровня персонажа" in note


def test_an_item_at_or_below_the_characters_level() -> None:
    assert "не выше уровня персонажа" in availability_note(_page("Weapon 0 · Price 1 gp"), 1)


def test_without_a_character_only_the_rule_itself_is_stated() -> None:
    note = availability_note(_page("Spell 3 · Traits: concentrate"), None)

    assert "на 5-м уровне" in note
    assert "открыт" not in note


@pytest.mark.parametrize(
    "header",
    ["Action · Traits: attack · Actions 1", "Condition · Duration -1", ""],
)
def test_pages_without_a_level_get_no_note(header) -> None:
    assert availability_note(_page(header), 3) is None


def test_a_continuation_chunk_without_the_stat_line_gets_no_note() -> None:
    """Only a page's first chunk carries the stat line; guessing a level for
    the rest would be exactly the invention this exists to prevent."""
    chunk = {
        "id": "x2",
        "text": "When you have your shield implement raised, the bonuses...",
        "metadata": {"title": "Shield", "ruleset": "pf2e", "traits": ""},
    }

    assert availability_note(chunk, 3) is None


def test_another_ruleset_is_left_alone() -> None:
    """The rank-to-level table is Pathfinder's; a D&D page must not get it."""
    assert availability_note(_page("Spell 3 · Traits: x", ruleset="dnd5e"), 5) is None
