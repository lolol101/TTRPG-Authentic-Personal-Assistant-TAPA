"""The Russian layer laid over the Foundry packs (docs/rfc/0001).

The localisation keys each record by its English name, so the cases check
what the layer must never lose: the English record's licence and remaster
checks, the English name in the title, and the record itself when its
translation is missing or broken.
"""

import json

from app.foundry import convert_tree, entry_to_page, journal_to_pages
from app.translation import Localization

_SOURCE = "gnuraco/pf2r@abc"
_LICENSE = "Paizo Community Use Policy + OGL 1.0a"


def _entry(name: str = "Grapple", **system_overrides) -> dict:
    system = {
        "description": {
            "value": "<p>You attempt to grab a creature or object with your free hand.</p>"
        },
        "publication": {"license": "ORC", "remaster": True, "title": "Pathfinder Player Core"},
        "traits": {"value": ["attack"], "rarity": "common"},
    }
    system.update(system_overrides)
    return {"_id": "abc123", "name": name, "type": "action", "system": system}


def _journal() -> dict:
    return {
        "name": "GM Screen",
        "pages": [
            {
                "_id": "p1",
                "name": "Conditions",
                "text": {
                    "content": "<p>Blinded: you cannot see. All normal terrain is difficult.</p>"
                },
            },
            {
                "_id": "p2",
                "name": "Untranslated Page",
                "text": {"content": "<p>This page has no translation and stays in English.</p>"},
            },
        ],
    }


def _write_module(root, packs: dict[str, dict]) -> None:
    packs_dir = root / "data" / "community" / "pf2e" / "packs"
    packs_dir.mkdir(parents=True)
    for name, entries in packs.items():
        (packs_dir / f"pf2e.{name}.json").write_text(
            json.dumps({"label": name, "entries": entries}, ensure_ascii=False), encoding="utf-8"
        )


def _localization(tmp_path, packs: dict[str, dict], pack_names: dict[str, str] | None = None):
    module = tmp_path / "pf2r"
    _write_module(module, packs)
    return Localization(
        module / "data" / "community" / "pf2e" / "packs",
        source=_SOURCE,
        license=_LICENSE,
        pack_names=pack_names,
    )


_GRAPPLE_RU = {
    "Grapple": {
        "name": "Захват",
        "description": "<p>Вы пытаетесь схватить существо или предмет свободной рукой.</p>",
    }
}


def test_a_translated_entry_is_written_in_russian(tmp_path) -> None:
    localization = _localization(tmp_path, {"actions": _GRAPPLE_RU})

    page = entry_to_page(
        _entry(), pack="actions", relative_path="actions/grapple.json", localization=localization
    )

    assert page is not None
    assert "схватить существо" in page.body
    assert "grab a creature" not in page.body
    assert page.language == "ru"
    assert page.translation_source == _SOURCE
    assert page.translation_license == _LICENSE


def test_the_title_keeps_the_english_name_next_to_the_translation(tmp_path) -> None:
    """Questions arrive with English terms in them, and the citation leads
    to the English record: dropping the original name loses both."""
    localization = _localization(tmp_path, {"actions": _GRAPPLE_RU})

    page = entry_to_page(
        _entry(), pack="actions", relative_path="actions/grapple.json", localization=localization
    )

    assert page is not None
    assert page.title == "Захват (Grapple)"
    assert page.body.startswith("Захват (Grapple)")


def test_the_licence_stays_the_originals(tmp_path) -> None:
    localization = _localization(tmp_path, {"actions": _GRAPPLE_RU})

    page = entry_to_page(
        _entry(), pack="actions", relative_path="actions/grapple.json", localization=localization
    )

    assert page is not None
    assert page.license == "ORC"


def test_a_closed_record_stays_out_even_when_translated(tmp_path) -> None:
    localization = _localization(tmp_path, {"actions": _GRAPPLE_RU})
    closed = _entry(publication={"license": "Paizo", "remaster": True, "title": "x"})

    page = entry_to_page(
        closed, pack="actions", relative_path="actions/grapple.json", localization=localization
    )

    assert page is None


def test_an_untranslated_entry_stays_english(tmp_path) -> None:
    localization = _localization(tmp_path, {"actions": {}})

    page = entry_to_page(
        _entry(), pack="actions", relative_path="actions/grapple.json", localization=localization
    )

    assert page is not None
    assert "grab a creature" in page.body
    assert page.title == "Grapple"
    assert page.language == "en"
    assert page.translation_source == ""


def test_a_translation_that_strips_to_nothing_falls_back_to_english(tmp_path) -> None:
    broken = {"Grapple": {"name": "Захват", "description": "<p>@Localize[PF2E.X]</p>"}}
    localization = _localization(tmp_path, {"actions": broken})

    page = entry_to_page(
        _entry(), pack="actions", relative_path="actions/grapple.json", localization=localization
    )

    assert page is not None
    assert "grab a creature" in page.body
    assert page.language == "en"


def test_pack_directories_are_mapped_to_compendium_names(tmp_path) -> None:
    """The checkout keeps feats in "feats", the module ships "feats-srd"."""
    localization = _localization(
        tmp_path, {"feats-srd": _GRAPPLE_RU}, pack_names={"feats": "feats-srd"}
    )

    assert localization.entry("feats", "Grapple") is not None


def test_from_checkout_reads_pack_names_from_the_system_manifest(tmp_path) -> None:
    module = tmp_path / "pf2r"
    _write_module(module, {"feats-srd": _GRAPPLE_RU})
    system = tmp_path / "pf2e"
    system.mkdir()
    (system / "system.pf2e.json").write_text(
        json.dumps({"packs": [{"name": "feats-srd", "path": "packs/pf2e/feats"}]}),
        encoding="utf-8",
    )

    localization = Localization.from_checkout(
        module, system_root=system, source=_SOURCE, license=_LICENSE
    )

    assert localization.entry("feats", "Grapple") is not None


def test_journal_pages_are_translated_page_by_page(tmp_path) -> None:
    translations = {
        "GM Screen": {
            "name": "Ширма мастера",
            "pages": {
                "Conditions": {
                    "name": "Состояния",
                    "text": "<p>Слепота: вы не можете видеть. Местность становится сложной.</p>",
                }
            },
        }
    }
    localization = _localization(tmp_path, {"journals": translations})

    pages = journal_to_pages(
        _journal(), pack="journals", relative_path="journals/gm.json", localization=localization
    )

    translated, untranslated = pages
    assert translated.title == "Ширма мастера — Состояния (Conditions)"
    assert "Слепота" in translated.body
    assert translated.language == "ru"
    assert untranslated.title == "GM Screen — Untranslated Page"
    assert untranslated.language == "en"


def test_convert_tree_writes_translated_chunks_with_their_provenance(tmp_path) -> None:
    packs = tmp_path / "packs"
    (packs / "actions").mkdir(parents=True)
    (packs / "actions" / "grapple.json").write_text(json.dumps(_entry()), encoding="utf-8")
    (packs / "actions" / "shove.json").write_text(
        json.dumps({**_entry("Shove"), "_id": "def456"}), encoding="utf-8"
    )
    localization = _localization(tmp_path, {"actions": _GRAPPLE_RU})
    out = tmp_path / "chunks"

    convert_tree(packs, out, localization=localization)

    records = {
        r["title"]: r
        for r in map(json.loads, (out / "actions.jsonl").read_text(encoding="utf-8").splitlines())
    }
    assert records["Захват (Grapple)"]["language"] == "ru"
    assert records["Захват (Grapple)"]["translation_license"] == _LICENSE
    assert records["Shove"]["language"] == "en"
    assert records["Shove"]["translation_source"] == ""


def test_without_a_localization_the_corpus_is_unchanged(tmp_path) -> None:
    page = entry_to_page(_entry(), pack="actions", relative_path="actions/grapple.json")

    assert page is not None
    assert page.title == "Grapple"
    assert page.language is None
    assert page.translation_source == ""
