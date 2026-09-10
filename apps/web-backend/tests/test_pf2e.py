"""Mirrors apps/web-frontend/src/lib/pf2e.test.ts — same rules, same numbers.

If one side ever drifts from the other, one of these suites goes red.
"""

from app.core import pf2e


def test_untrained_gets_nothing_not_even_level() -> None:
    assert pf2e.proficiency_bonus("untrained", 12) == 0


def test_level_counts_once_trained() -> None:
    assert pf2e.proficiency_bonus("trained", 1) == 3
    assert pf2e.proficiency_bonus("expert", 3) == 7
    assert pf2e.proficiency_bonus("master", 10) == 16
    assert pf2e.proficiency_bonus("legendary", 20) == 28


def test_stat_total_sums_every_component() -> None:
    assert pf2e.stat_total(ability_mod=4, level=3, rank="expert", item=1, temporary=2) == 14


def test_stat_total_applies_base_for_ac_and_class_dc() -> None:
    assert pf2e.stat_total(ability_mod=2, level=1, rank="trained", item=2, base=10) == 17


def test_stat_total_applies_armor_check_penalty() -> None:
    assert pf2e.stat_total(ability_mod=3, level=5, rank="trained", armor_penalty=-2) == 8


def test_untrained_skill_is_just_the_ability_modifier() -> None:
    assert pf2e.stat_total(ability_mod=-1, level=8, rank="untrained") == -1


def test_max_hp_applies_class_and_constitution_every_level() -> None:
    assert pf2e.max_hp(ancestry=8, per_level=10, con_mod=3, level=5) == 8 + 13 * 5


def test_max_hp_adds_bonuses_and_subtracts_penalty() -> None:
    result = pf2e.max_hp(
        ancestry=8, per_level=6, con_mod=1, level=2, item=4, other=3, penalty=5
    )
    assert result == 8 + 7 * 2 + 4 + 3 - 5


def test_only_strength_and_dexterity_skills_take_the_armor_penalty() -> None:
    assert pf2e.has_armor_penalty("athletics")
    assert pf2e.has_armor_penalty("stealth")
    assert not pf2e.has_armor_penalty("diplomacy")
