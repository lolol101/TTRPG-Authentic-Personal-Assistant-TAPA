"""Tests for the Foundry VTT pack converter.

The cases here are drawn from measurements of the real dataset rather than
imagination: 14369 bare @UUID references carry a name in their tail (only 18
carry an opaque id), 4818 @Check/@Damage/@Template enrichers carry the
mechanics a rules question actually turns on, and 45 entries are nothing but
a @Localize key whose words live in a translation file we do not ship.
"""

import json

import pytest

from app.foundry import (
    LICENSED,
    convert_tree,
    entry_to_page,
    to_text,
)


def _entry(**overrides):
    """A minimal licensed, remastered entry; overrides go into system."""
    system = {
        "description": {"value": "<p>A plain sentence long enough to be kept as text.</p>"},
        "publication": {"license": "ORC", "remaster": True, "title": "Pathfinder Player Core"},
        "traits": {"value": ["fire", "concentrate"], "rarity": "common"},
        "level": {"value": 3},
    }
    system.update(overrides.pop("system", {}))
    entry = {"_id": "abc123", "name": "Test Entry", "type": "spell", "system": system}
    entry.update(overrides)
    return entry


# --- enricher conversion -------------------------------------------------


def test_labelled_uuid_becomes_its_label() -> None:
    html = "<p>Use @UUID[Compendium.pf2e.feats.Item.xY]{Power Attack}.</p>"

    assert "Power Attack" in to_text(html)


def test_bare_uuid_becomes_the_name_in_its_tail() -> None:
    """The measured failure: dropping these turned "You gain the Domain
    Initiate cleric feat" into "You gain the cleric feat" — the opposite of
    the rule, not merely a thinner version of it."""
    html = "<p>You gain the @UUID[Compendium.pf2e.feats-srd.Item.Domain Initiate] feat.</p>"

    text = to_text(html)

    assert "Domain Initiate" in text
    assert "Compendium" not in text


def test_bare_uuid_with_an_opaque_id_is_dropped_not_printed() -> None:
    text = to_text("<p>See @UUID[Compendium.pf2e.feats.Item.AbCdEfGhIjKlMnOp] for more.</p>")

    assert "AbCdEfGhIjKlMnOp" not in text


def test_check_keeps_the_dc_and_the_save() -> None:
    text = to_text("<p>Attempt a @Check[reflex|dc:24|basic] save.</p>")

    assert "Reflex" in text
    assert "24" in text
    assert "basic" in text.lower()


def test_check_against_a_spell_dc_says_so() -> None:
    text = to_text("<p>@Check[fortitude|against:class-spell|basic]</p>")

    assert "Fortitude" in text
    assert "spell DC" in text


def test_damage_keeps_dice_and_type() -> None:
    """The inner bracket is part of the payload: @Damage[6d6[fire]]."""
    text = to_text("<p>You deal @Damage[6d6[fire]] damage.</p>")

    assert "6d6" in text
    assert "fire" in text


def test_damage_with_a_parenthesised_formula_survives() -> None:
    text = to_text("<p>Restores @Damage[(1d8+8)[healing]] HP.</p>")

    assert "1d8+8" in text
    assert "healing" in text


def test_template_becomes_a_readable_area() -> None:
    assert "15-foot burst" in to_text("<p>@Template[burst|distance:15]</p>")


def test_template_tolerates_the_type_prefix() -> None:
    assert "30-foot emanation" in to_text("<p>@Template[type:emanation|distance:30]</p>")


def test_html_tags_are_stripped_but_list_items_stay_separate() -> None:
    text = to_text("<ul><li><p>First option.</p></li><li><p>Second option.</p></li></ul>")

    assert "<" not in text
    assert "First option." in text
    assert "Second option." in text
    # Without a break the two run together into "First option.Second option."
    assert "option.Second" not in text.replace(" ", "")


def test_unknown_enrichers_do_not_leak_markup() -> None:
    text = to_text("<p>Text @SomethingNew[weird|payload]{Shown} more.</p>")

    assert "@" not in text
    assert "[" not in text


# --- inline [[...]] rolls, a second markup family found in the real data --


def test_inline_action_roll_becomes_the_action_name() -> None:
    """Measured in the corpus: 917 of these across 622 entries, and the
    first real conversion left "[[/act grapple]]{Athletics}" sitting in the
    middle of the Grapple rules."""
    text = to_text("<p>Attempt an [[/act grapple]]{Athletics} check.</p>")

    assert "Athletics" in text
    assert "[[" not in text and "/act" not in text


def test_inline_action_without_a_label_still_names_the_action() -> None:
    text = to_text("<p>You can [[/act demoralize]] the target.</p>")

    assert "Demoralize" in text
    assert "[" not in text


def test_inline_roll_keeps_the_formula_and_drops_the_flavour_tag() -> None:
    text = to_text("<p>Recharge in [[/r 1d4 #Recharge Blazing Soul]] rounds.</p>")

    assert "1d4" in text
    assert "#" not in text and "[[" not in text


def test_inline_roll_prefers_its_display_label() -> None:
    text = to_text("<p>Deals [[/r (@actor.level)d6]]{1d6 damage per level}.</p>")

    assert "1d6 damage per level" in text
    assert "@actor" not in text


def test_nested_brackets_inside_an_inline_roll_are_matched() -> None:
    text = to_text("<p>Regains [[/r 4d8[healing] #Treat Wounds]] Hit Points.</p>")

    assert "4d8" in text
    assert "healing" in text
    assert "[" not in text and "#" not in text


def test_a_level_scaling_damage_formula_does_not_leak_machinery() -> None:
    """242 records leaked formula soup like
    "ternary(gte(@actor.level, 18), 7, ...)d6 acid" on the first real run.
    The number genuinely depends on level, so say that rather than print
    the expression a player cannot evaluate."""
    html = "<p>Takes @Damage[ternary(gte(@actor.level, 18), 7, 5)d6[acid]] damage.</p>"

    text = to_text(html)

    assert "@actor" not in text
    assert "ternary" not in text
    assert "acid" in text
    assert "level" in text.lower()


def test_a_scaling_formula_with_options_suffix_is_also_cleaned() -> None:
    html = "<p>@Damage[max(5,ceil(@actor.level/2))d4[fire]|options:area-damage] damage.</p>"

    text = to_text(html)

    assert "@actor" not in text
    assert "options:" not in text
    assert "fire" in text


def test_gm_and_blind_rolls_are_handled_too() -> None:
    text = to_text("<p>Wait [[/gmr 1d4+1#Lost Omens]] and [[/br 1d6]] rounds.</p>")

    assert "1d4+1" in text
    assert "1d6" in text
    assert "[[" not in text


# --- entry filtering -----------------------------------------------------


def test_a_licensed_remastered_entry_is_kept() -> None:
    page = entry_to_page(_entry(), pack="spells", relative_path="spells/test.json")

    assert page is not None
    assert page.title == "Test Entry"
    assert page.category == "spells"
    assert page.source_book == "Pathfinder Player Core"
    assert page.traits == ["fire", "concentrate"]


@pytest.mark.parametrize("licence", ["", None, "Paizo", "proprietary"])
def test_an_entry_without_an_open_licence_is_refused(licence) -> None:
    """The project indexes open content only, and the dataset stamps the
    licence on every entry — so this is checkable rather than assumed."""
    entry = _entry()
    entry["system"]["publication"]["license"] = licence

    assert entry_to_page(entry, pack="spells", relative_path="p.json") is None


def test_every_accepted_licence_is_an_open_one() -> None:
    assert set(LICENSED) == {"ORC", "OGL"}


def test_a_legacy_entry_is_refused() -> None:
    entry = _entry()
    entry["system"]["publication"]["remaster"] = False

    assert entry_to_page(entry, pack="spells", relative_path="p.json") is None


def test_an_entry_that_is_only_a_localize_key_is_refused() -> None:
    """Its words live in a translation file this project does not ship, so
    what would be indexed is an empty husk with a plausible length."""
    entry = _entry()
    entry["system"]["description"]["value"] = "<p>@Localize[PF2E.NPC.Glossary.PowerAttack]</p>"

    assert entry_to_page(entry, pack="spells", relative_path="p.json") is None


def test_an_entry_with_no_description_is_refused() -> None:
    entry = _entry()
    entry["system"]["description"]["value"] = ""

    assert entry_to_page(entry, pack="spells", relative_path="p.json") is None


def test_the_text_carries_the_name_and_level_for_retrieval() -> None:
    page = entry_to_page(_entry(), pack="spells", relative_path="p.json")

    assert page is not None
    assert "Test Entry" in page.body
    assert "3" in page.body


def test_a_bare_cast_number_is_spelled_out_as_actions() -> None:
    """860 spells store "2" for a two-action cast; printed raw it reads as
    "Cast 2", which tells a player nothing about the action cost."""
    entry = _entry()
    entry["system"]["time"] = {"value": "2"}

    page = entry_to_page(entry, pack="spells", relative_path="p.json")

    assert page is not None
    assert "Cast 2 actions" in page.body


def test_a_single_action_cast_is_not_pluralised() -> None:
    entry = _entry()
    entry["system"]["time"] = {"value": "1"}

    page = entry_to_page(entry, pack="spells", relative_path="p.json")

    assert page is not None
    assert "Cast 1 action" in page.body
    assert "1 actions" not in page.body


def test_a_plain_number_field_does_not_crash_the_run() -> None:
    """Real data, found by running it: 350 thrown-weapon entries store
    "range": 20 as a bare int rather than {"value": 20}, and 668 store None.
    Assuming the dict shape crashed the whole conversion on the first one."""
    entry = _entry()
    entry["system"]["range"] = 20

    page = entry_to_page(entry, pack="equipment", relative_path="p.json")

    assert page is not None
    assert "Range 20" in page.body


def test_a_null_field_is_simply_absent() -> None:
    entry = _entry()
    entry["system"]["range"] = None

    page = entry_to_page(entry, pack="equipment", relative_path="p.json")

    assert page is not None
    assert "Range" not in page.body


def test_a_worded_cast_time_is_left_alone() -> None:
    entry = _entry()
    entry["system"]["time"] = {"value": "10 minutes"}

    page = entry_to_page(entry, pack="spells", relative_path="p.json")

    assert page is not None
    assert "Cast 10 minutes" in page.body


def test_the_url_points_at_the_actual_source_file() -> None:
    page = entry_to_page(_entry(), pack="spells", relative_path="spells/focus/x.json")

    assert page is not None
    assert page.url.startswith("https://github.com/foundryvtt/pf2e")
    assert "spells/focus/x.json" in page.url


def test_the_url_is_pinned_to_the_ref_the_data_came_from() -> None:
    """Citations are shown to players, and the first run pinned them to
    "master", where these paths do not exist — every one of 13494 links
    answered 404. A commit is better than a branch: a branch moves on.
    """
    page = entry_to_page(
        _entry(), pack="spells", relative_path="spells/x.json", ref="abc1234"
    )

    assert page is not None
    assert "/blob/abc1234/" in page.url


# --- tree conversion -----------------------------------------------------


def _write(root, relative: str, entry: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entry), encoding="utf-8")


def test_convert_tree_writes_one_jsonl_per_pack(tmp_path) -> None:
    packs = tmp_path / "packs"
    _write(packs, "spells/one.json", _entry(name="Spell One"))
    _write(packs, "feats/two.json", _entry(name="Feat Two"))
    out = tmp_path / "chunks"

    counts = convert_tree(packs, out)

    assert counts == {"spells": 1, "feats": 1}
    assert (out / "spells.jsonl").is_file()
    assert (out / "feats.jsonl").is_file()


def test_convert_tree_skips_foundry_automation_packs(tmp_path) -> None:
    """*-effects packs hold Foundry's rule automation, not rules prose."""
    packs = tmp_path / "packs"
    _write(packs, "spell-effects/e.json", _entry(name="Spell Effect: X"))
    _write(packs, "spells/s.json", _entry(name="Real Spell"))

    counts = convert_tree(packs, tmp_path / "chunks")

    assert "spell-effects" not in counts
    assert counts["spells"] == 1


def test_convert_tree_ignores_folder_metadata_files(tmp_path) -> None:
    packs = tmp_path / "packs"
    _write(packs, "spells/_folders.json", {"name": "not an entry"})
    _write(packs, "spells/s.json", _entry())

    assert convert_tree(packs, tmp_path / "chunks") == {"spells": 1}


def test_written_records_carry_english_and_the_pf2e_ruleset(tmp_path) -> None:
    """The pf2.ru corpus was Russian; mixing the two silently would make
    "why is this answer in English" impossible to explain from the index."""
    packs = tmp_path / "packs"
    _write(packs, "spells/s.json", _entry())
    out = tmp_path / "chunks"

    convert_tree(packs, out)
    record = json.loads((out / "spells.jsonl").read_text(encoding="utf-8").splitlines()[0])

    assert record["language"] == "en"
    assert record["category"] == "spells"
    assert record["source_book"] == "Pathfinder Player Core"


def test_ids_are_stable_across_runs(tmp_path) -> None:
    """Re-running must upsert over the same rows rather than duplicate them."""
    packs = tmp_path / "packs"
    _write(packs, "spells/s.json", _entry())
    out = tmp_path / "chunks"

    convert_tree(packs, out)
    first = (out / "spells.jsonl").read_text(encoding="utf-8")
    convert_tree(packs, out)
    second = (out / "spells.jsonl").read_text(encoding="utf-8")

    assert first == second


def test_two_entries_never_collide_on_one_id(tmp_path) -> None:
    packs = tmp_path / "packs"
    _write(packs, "spells/a.json", _entry(name="A"))
    _write(packs, "spells/b.json", _entry(name="B"))
    out = tmp_path / "chunks"

    convert_tree(packs, out)
    lines = (out / "spells.jsonl").read_text(encoding="utf-8").splitlines()
    ids = [json.loads(line)["id"] for line in lines]

    assert len(ids) == len(set(ids)) == 2
