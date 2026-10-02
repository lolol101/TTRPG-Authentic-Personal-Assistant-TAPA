"""Russian text for Foundry pack entries, from a Babele localisation module.

The localisation (gnuraco/pf2r, see docs/rfc/0001) ships one JSON file per
compendium, keyed by the English name of each record — the same records the
converter already reads. So the translation is laid over a record rather than
read on its own: remaster and licence are still checked on the English
original, and a record with no translation stays in English instead of
dropping out of the corpus.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)

#: Where a Babele module keeps the system's compendium translations.
_PACKS_SUBDIR = Path("data") / "community" / "pf2e" / "packs"


@dataclass(frozen=True)
class Translation:
    name: str
    html: str


class Localization:
    """Translations of one module checkout, loaded pack by pack on demand."""

    def __init__(
        self,
        packs_dir: Path,
        *,
        source: str,
        license: str,
        pack_names: dict[str, str] | None = None,
    ) -> None:
        self.packs_dir = packs_dir
        self.source = source
        self.license = license
        # Pack directory in the system checkout -> compendium name: "feats"
        # is shipped as "feats-srd", "actions" as "actionspf2e".
        self._pack_names = pack_names or {}
        self._loaded: dict[str, dict] = {}

    @classmethod
    def from_checkout(
        cls, module_root: Path, *, system_root: Path, source: str, license: str
    ) -> Localization:
        packs_dir = module_root / _PACKS_SUBDIR
        if not packs_dir.is_dir():
            raise FileNotFoundError(f"No Babele packs under {packs_dir}")
        return cls(
            packs_dir,
            source=source,
            license=license,
            pack_names=_pack_names(system_root / "system.pf2e.json"),
        )

    def entry(self, pack: str, name: str) -> Translation | None:
        translated = self._entries(pack).get(name)
        if not isinstance(translated, dict):
            return None
        html = translated.get("description")
        if not isinstance(html, str) or not html.strip():
            return None
        return Translation(name=str(translated.get("name") or name), html=html)

    def journal_name(self, pack: str, journal: str) -> str | None:
        translated = self._entries(pack).get(journal)
        name = translated.get("name") if isinstance(translated, dict) else None
        return str(name) if name else None

    def page(self, pack: str, journal: str, page: str) -> Translation | None:
        translated = self._entries(pack).get(journal)
        pages = translated.get("pages") if isinstance(translated, dict) else None
        found = pages.get(page) if isinstance(pages, dict) else None
        if not isinstance(found, dict):
            return None
        html = found.get("text")
        if not isinstance(html, str) or not html.strip():
            return None
        return Translation(name=str(found.get("name") or page), html=html)

    def _entries(self, pack: str) -> dict:
        if pack not in self._loaded:
            self._loaded[pack] = self._read(pack)
        return self._loaded[pack]

    def _read(self, pack: str) -> dict:
        path = self.packs_dir / f"pf2e.{self._pack_names.get(pack, pack)}.json"
        if not path.exists():
            return {}
        try:
            entries = json.loads(path.read_text(encoding="utf-8")).get("entries")
        except (json.JSONDecodeError, OSError, AttributeError) as exc:
            _log.warning("Skipping translation %s: %s", path, exc)
            return {}
        return entries if isinstance(entries, dict) else {}


def _pack_names(system_json: Path) -> dict[str, str]:
    if not system_json.exists():
        return {}
    packs = json.loads(system_json.read_text(encoding="utf-8")).get("packs") or []
    return {
        Path(pack["path"]).name: pack["name"]
        for pack in packs
        if isinstance(pack, dict) and pack.get("path") and pack.get("name")
    }
