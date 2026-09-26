"""Convert the Foundry VTT PF2e packs into the same chunks the crawler makes.

An offline source that needs no crawling: the packs are structured JSON in a
git repository, so there is no sitemap, no rate limit and no ban to survive.
Every entry also carries its own licence and a remaster flag, which turns two
things this project could previously only assume into things it can check —
that only open content is indexed, and that superseded rules stay out.

Output is deliberately the same `Chunk` shape the pf2.ru pipeline writes, so
llm-service ingests it unchanged.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from pathlib import Path

from bs4 import BeautifulSoup

from app.chunker import chunk_page
from app.models import ParsedPage

_log = logging.getLogger(__name__)

#: Licences whose content this project is allowed to index. The dataset
#: stamps one on every entry; anything else is left alone.
LICENSED = ("ORC", "OGL")

#: Foundry's rule-automation entries: active-effect bookkeeping with names
#: like "Spell Effect: Haste" and no prose a player would ever read.
EFFECT_PACKS = frozenset(
    {
        "feat-effects",
        "equipment-effects",
        "spell-effects",
        "bestiary-effects",
        "other-effects",
        "campaign-effects",
    }
)

#: Below this, what survived stripping is a fragment rather than a rule —
#: in practice a @Localize key whose words ship in a translation file.
MIN_TEXT_CHARS = 40

_SOURCE_REPO = "https://github.com/foundryvtt/pf2e"

#: The branch the packs live on. Only a fallback: a citation should name the
#: commit the text actually came from, because a branch moves and the link
#: then describes content that is no longer there.
DEFAULT_REF = "v14-dev"

_FOUNDRY_ID = re.compile(r"^[A-Za-z0-9]{16}$")
#: Expression machinery inside a damage formula: the value depends on the
#: character, so no fixed number can be printed for it.
_SCALING = re.compile(r"@(actor|item)\.[\w.]+|\b(ternary|gte|lte|floor|ceil|max|min)\b")
_UUID_LABELLED = re.compile(r"@UUID\[[^\]]+\]\{([^}]*)\}")
_UUID_BARE = re.compile(r"@UUID\[([^\]]+)\]")
_CHECK = re.compile(r"@Check\[([^\]]+)\](?:\{([^}]*)\})?")
_TEMPLATE = re.compile(r"@Template\[([^\]]+)\](?:\{([^}]*)\})?")
_ANY_ENRICHER = re.compile(r"@\w+\[[^\]]*\](?:\{([^}]*)\})?")

_WHITESPACE = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def _check_to_text(match: re.Match[str]) -> str:
    """@Check[reflex|dc:24|basic] -> "basic Reflex DC 24"."""
    if match.group(2):
        return match.group(2)

    parts = match.group(1).split("|")
    statistic = parts[0].replace("-", " ").title()
    basic = "basic " if "basic" in parts else ""
    dc = ""
    for part in parts[1:]:
        if part.startswith("dc:"):
            dc = f" DC {part[3:]}"
        elif part.startswith("against:"):
            # The DC is the caster's own; naming it beats printing a slug.
            dc = " against your spell DC"
    return f"{basic}{statistic}{dc}"


def _damage_to_text(payload: str, label: str) -> str:
    """@Damage[6d6[fire]] -> "6d6 fire"; the inner bracket is the damage type.

    Some formulas scale with the character — "ternary(gte(@actor.level, 18),
    7, 5)d6[acid]" — and printing them raw put expression soup into 242
    records. A player cannot evaluate that, so name the type and say it
    scales instead of pretending there is a fixed number.
    """
    if label:
        return label

    payload = payload.split("|")[0]  # drop |options:area-damage and friends
    formula, _, kind = payload.partition("[")
    kind = kind.rstrip("]").replace(",", " ").strip()
    if kind.startswith("@") or "." in kind:
        kind = ""

    if _SCALING.search(formula):
        dice = re.search(r"d\d+", formula)
        size = f" {dice.group()}" if dice else ""
        return f"{kind}{size} damage scaling with your level".strip()

    return f"{formula.strip('() ')} {kind}".strip()


def _template_to_text(match: re.Match[str]) -> str:
    """@Template[burst|distance:15] -> "15-foot burst"."""
    if match.group(2):
        return match.group(2)

    shape = ""
    distance = ""
    for part in match.group(1).split("|"):
        if part.startswith("distance:"):
            distance = part[len("distance:") :]
        else:
            shape = part.removeprefix("type:")
    return f"{distance}-foot {shape}".strip("- ") if distance else shape


def _bare_uuid_to_text(match: re.Match[str]) -> str:
    """A reference with no label still names its target in the last segment.

    Dropping these silently inverted rules: "You gain the Domain Initiate
    cleric feat" became "You gain the cleric feat". Only the handful whose
    tail is an opaque Foundry id are worth dropping.
    """
    tail = match.group(1).rsplit(".", 1)[-1]
    return "" if _FOUNDRY_ID.match(tail) else tail


def _inline_roll_to_text(payload: str, label: str) -> str:
    """[[/act grapple]]{Athletics} -> "Athletics"; [[/r 1d4 #tag]] -> "1d4".

    A second markup family alongside the @-enrichers, and easy to miss: the
    first pass over real data left "[[/act grapple]]{Athletics}" sitting in
    the middle of the Grapple rules.
    """
    if label:
        return label

    payload = payload.strip()
    command, _, rest = payload.partition(" ")
    rest = rest.split("#", 1)[0].strip()

    if command == "/act":
        # The action's own name is the readable part: "/act demoralize".
        name = rest.split(" dc=")[0].replace("-", " ").strip()
        return name.title()
    if command in ("/r", "/gmr", "/br"):
        # Same "formula[type]" shape a @Damage payload has, so read it the
        # same way rather than growing a second dialect of the same parse.
        return _damage_to_text(rest, "")
    return rest


def _replace_bracketed(text: str, prefix: str, handler) -> str:
    """Replace `prefix[...]{label}` forms, matching brackets by counting.

    A regex cannot do this: payloads nest, as in @Damage[4d8[healing]] and
    [[/r 4d8[healing] #tag]], and a non-greedy match stops at the first
    inner bracket — which is how formula fragments leaked into the corpus.
    """
    opens = prefix.count("[")
    out: list[str] = []
    index = 0

    while True:
        start = text.find(prefix, index)
        if start == -1:
            out.append(text[index:])
            return "".join(out)

        out.append(text[index:start])
        depth = 0
        cursor = start + len(prefix) - opens
        end = -1
        while cursor < len(text):
            if text[cursor] == "[":
                depth += 1
            elif text[cursor] == "]":
                depth -= 1
                if depth == 0:
                    end = cursor
                    break
            cursor += 1

        if end == -1:  # unbalanced; leave the rest untouched rather than guess
            out.append(text[start:])
            return "".join(out)

        payload = text[start + len(prefix) : end - (opens - 1)]
        label = ""
        after = end + 1
        if after < len(text) and text[after] == "{":
            close = text.find("}", after)
            if close != -1:
                label = text[after + 1 : close]
                after = close + 1

        out.append(handler(payload, label))
        index = after


def to_text(html: str) -> str:
    """Foundry's HTML-plus-enricher description as plain, readable prose."""
    text = _UUID_LABELLED.sub(lambda m: m.group(1), html)
    text = _UUID_BARE.sub(_bare_uuid_to_text, text)
    text = _replace_bracketed(text, "@Damage[", _damage_to_text)
    text = _replace_bracketed(text, "[[", _inline_roll_to_text)
    text = _CHECK.sub(_check_to_text, text)
    text = _TEMPLATE.sub(_template_to_text, text)
    # Whatever enricher is left is one we do not translate; keep its display
    # label if it has one so the sentence still reads, drop the machinery.
    text = _ANY_ENRICHER.sub(lambda m: m.group(1) or "", text)

    # Block elements must not fuse two sentences into "First.Second".
    soup = BeautifulSoup(text, "lxml")
    for block in soup.find_all(["p", "li", "div", "br", "tr", "h1", "h2", "h3", "h4"]):
        block.append("\n")
    text = soup.get_text()

    text = _WHITESPACE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANK_LINES.sub("\n\n", text).strip()


def _spell_out_actions(value: str) -> str:
    """ "2" is an action cost, not a duration: 860 spells store it that way.

    Printed raw it becomes "Cast 2", which says nothing to a player asking
    what an action costs. Worded values ("10 minutes", "reaction") already
    read correctly and are left alone.
    """
    if not value.isdigit():
        return value
    return f"{value} action" if value == "1" else f"{value} actions"


def _value_of(system: dict, field: str) -> str | int | None:
    """One field's value, whatever shape the dataset stores it in.

    Mostly {"value": x}, but thrown weapons store "range": 20 as a bare int
    and many entries store null. Assuming the dict shape crashed the first
    real run outright.
    """
    raw = system.get(field)
    if isinstance(raw, dict):
        return raw.get("value")
    return raw


#: Foundry's action costs. "passive" is the absence of one, so it prints
#: nothing rather than the word.
_ACTION_WORDS = {"reaction": "Reaction", "free": "Free Action"}

_ISO_UNITS = {"H": "hour", "M": "minute", "S": "second"}
_ISO_DURATION = re.compile(r"^PT(\d+)([HMS])$")

#: PF2e writes a tenth of a Bulk as "L" for light, and no Bulk at all as a
#: dash. The dataset stores them as 0.1 and 0.
_BULK_WORDS = {0.1: "L", 0: "—"}


def _action_cost(system: dict) -> str:
    """ "Actions 2", "Reaction", or nothing at all for a passive ability."""
    kind = str(_value_of(system, "actionType") or "")
    if kind in _ACTION_WORDS:
        return _ACTION_WORDS[kind]
    if kind != "action":
        return ""

    count = _value_of(system, "actions")
    if not isinstance(count, int):
        return ""
    return f"Actions {count}"


def _frequency_text(raw: object) -> str:
    """{"max": 1, "per": "PT10M"} -> "once per 10 minutes".

    The period is ISO-8601 for anything shorter than a day, which is not a
    thing to put in front of a player: "Frequency once per PT10M" was the
    alternative.
    """
    if not isinstance(raw, dict):
        return ""
    per = str(raw.get("per") or "").strip()
    if not per:
        return ""

    match = _ISO_DURATION.match(per)
    if match:
        amount, unit_letter = int(match.group(1)), match.group(2)
        unit = _ISO_UNITS[unit_letter]
        per = unit if amount == 1 else f"{amount} {unit}s"

    max_uses = raw.get("max")
    times = "once" if max_uses in (1, None) else f"{max_uses} times"
    return f"{times} per {per}"


def _price_text(raw: object) -> str:
    """{"value": {"gp": 50}} -> "50 gp". Order follows the coin hierarchy."""
    if not isinstance(raw, dict):
        return ""
    coins = raw.get("value")
    if not isinstance(coins, dict):
        return ""
    parts = [f"{coins[coin]} {coin}" for coin in ("pp", "gp", "sp", "cp") if coins.get(coin)]
    return ", ".join(parts)


def _bulk_text(raw: object) -> str:
    value = raw.get("value") if isinstance(raw, dict) else raw
    if not isinstance(value, (int, float)):
        return ""
    return _BULK_WORDS.get(value, str(value))


def _prerequisites_text(system: dict) -> str:
    """{"value": [{"value": "trained in Athletics"}]} -> the joined list.

    Half the entries carrying the field store an empty list, and the items
    are one-key dicts rather than strings.
    """
    raw = system.get("prerequisites")
    items = raw.get("value") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return ""

    names = []
    for item in items:
        text = item.get("value") if isinstance(item, dict) else item
        text = str(text or "").strip()
        if text:
            names.append(text)
    return "; ".join(names)


def _save_text(raw: object) -> str:
    """{"save": {"basic": true, "statistic": "reflex"}} -> "basic Reflex"."""
    if not isinstance(raw, dict):
        return ""
    save = raw.get("save")
    if not isinstance(save, dict):
        return ""
    statistic = str(save.get("statistic") or "").strip()
    if not statistic:
        return ""
    return f"{'basic ' if save.get('basic') else ''}{statistic.title()}"


def _area_text(raw: object) -> str:
    """{"type": "burst", "value": 20} -> "20-foot burst"."""
    if not isinstance(raw, dict):
        return ""
    details = str(raw.get("details") or "").strip()
    if details:
        return details
    shape = str(raw.get("type") or "").strip()
    value = raw.get("value")
    if value and shape:
        return f"{value}-foot {shape}"
    return shape or ""


def _header(entry: dict, text_parts: list[str]) -> None:
    """Prepend the stat block: what a page states as a field, not as prose.

    A spell's own description rarely contains the words "spell", its level or
    its traits, yet those are exactly what a question names. The same holds
    for everything a player copies onto a sheet — an action cost, a price, a
    prerequisite: each is stated once as a field and never repeated in the
    description. Reported live: the assistant left those card fields empty,
    and measured on the built index, only 1.8% of feat chunks mentioned a
    prerequisite at all — there was nothing there for it to copy.
    """
    system = entry.get("system") or {}
    facts: list[str] = []

    kind = entry.get("type")
    level = _value_of(system, "level")
    if kind and level is not None:
        facts.append(f"{kind.title()} {level}")
    elif kind:
        facts.append(kind.title())

    traits_field = system.get("traits") if isinstance(system.get("traits"), dict) else {}
    traits = traits_field.get("value") or []
    if traits:
        facts.append("Traits: " + ", ".join(str(t) for t in traits))

    # Common is the default and says nothing; the other three are the point
    # of the field — a rare feat is not one to hand a player unasked.
    rarity = str(traits_field.get("rarity") or "").strip()
    if rarity and rarity != "common":
        facts.append(f"Rarity {rarity}")

    traditions = traits_field.get("traditions") or []
    if traditions:
        facts.append("Traditions: " + ", ".join(str(t) for t in traditions))

    # Which kind of slot a feat fills — class, ancestry, skill, general. The
    # sheet keeps those in separate groups, so this is what decides where a
    # chosen feat belongs.
    category = system.get("category")
    if isinstance(category, str) and category.strip():
        facts.append(f"Category {category.strip()}")

    action_cost = _action_cost(system)
    if action_cost:
        facts.append(action_cost)

    for field, label, render in (
        ("frequency", "Frequency", _frequency_text),
        ("price", "Price", _price_text),
        ("bulk", "Bulk", _bulk_text),
        ("defense", "Saving Throw", _save_text),
        ("area", "Area", _area_text),
    ):
        rendered = render(system.get(field))
        if rendered:
            facts.append(f"{label} {rendered}")

    for field, label in (("usage", "Usage"), ("hands", "Hands"), ("target", "Targets")):
        value = _value_of(system, field)
        text = str(value).strip() if value not in (None, "") else ""
        if text:
            facts.append(f"{label} {text.replace('-', ' ')}")

    for field, label in (("time", "Cast"), ("range", "Range"), ("duration", "Duration")):
        value = _value_of(system, field)
        if value:
            facts.append(f"{label} {_spell_out_actions(str(value))}")

    text_parts.append(entry["name"])
    if facts:
        text_parts.append(" · ".join(facts))

    # Own lines: both run long enough to read badly inside the ` · ` run,
    # and both are conditions to check before taking the thing at all.
    prerequisites = _prerequisites_text(system)
    if prerequisites:
        text_parts.append(f"Prerequisites {prerequisites}")

    requirements = str(_value_of(system, "requirements") or "").strip()
    if requirements:
        text_parts.append(f"Requirements {requirements}")


def _publication_of(holder: object) -> dict:
    """The publication block of an entry or of a journal page, if it has one."""
    if not isinstance(holder, dict):
        return {}
    system = holder.get("system")
    if not isinstance(system, dict):
        return {}
    publication = system.get("publication") or system.get("source") or {}
    return publication if isinstance(publication, dict) else {}


def _is_indexable(publication: dict) -> bool:
    """Open and remastered — the two things the corpus promises about itself.

    Kept as one named check because journal pages are stamped in the same
    place items are, and the promise must not quietly differ between them.
    """
    return publication.get("license") in LICENSED and publication.get("remaster") is True


def journal_to_pages(
    entry: dict, *, pack: str, relative_path: str, ref: str = DEFAULT_REF
) -> list[ParsedPage]:
    """A JournalEntry's text pages, one ParsedPage each.

    Foundry keeps rules chapters, setting and GM guidance as journals rather
    than items: no `system` of their own, a list of `pages`, each holding its
    HTML in `text.content`. `entry_to_page` reads none of that and returns
    None on the first check, which is why the corpus has held statblocks and
    nothing that reads like a book.

    Licence and remaster are taken from the page, falling back to the entry.
    A page stamped with neither stays out: an unstamped page is not evidence
    that the text is open, and this corpus is worth exactly what that
    guarantee is worth.
    """
    if not isinstance(entry, dict):
        return []
    pages = entry.get("pages")
    if not isinstance(pages, list):
        return []

    entry_publication = _publication_of(entry)
    entry_name = str(entry.get("name") or "").strip()

    parsed: list[ParsedPage] = []
    for page in pages:
        if not isinstance(page, dict):
            continue

        publication = _publication_of(page) or entry_publication
        if not _is_indexable(publication):
            continue

        text = page.get("text")
        content = text.get("content") if isinstance(text, dict) else None
        body = to_text(str(content or ""))
        if len(body) < MIN_TEXT_CHARS:
            continue

        page_name = str(page.get("name") or "").strip()
        # A one-page journal usually repeats its own name; two identical
        # halves in a title only cost the embedding room to say less.
        names = [name for name in (entry_name, page_name) if name]
        title = " — ".join(dict.fromkeys(names))

        parsed.append(
            ParsedPage(
                url=f"{_SOURCE_REPO}/blob/{ref}/packs/pf2e/{relative_path}",
                category=pack,
                title=title,
                source_book=publication.get("title") or None,
                traits=[],
                body=body,
                fetched_at="",
            )
        )
    return parsed


def entry_to_page(
    entry: dict, *, pack: str, relative_path: str, ref: str = DEFAULT_REF
) -> ParsedPage | None:
    """One pack entry as a ParsedPage, or None if it must not be indexed."""
    if not isinstance(entry, dict) or "name" not in entry:
        return None

    system = entry.get("system")
    if not isinstance(system, dict):
        return None

    publication = _publication_of(entry)
    if not _is_indexable(publication):
        return None

    body = to_text(str(_value_of(system, "description") or ""))
    if len(body) < MIN_TEXT_CHARS:
        return None

    parts: list[str] = []
    _header(entry, parts)
    parts.append(body)

    return ParsedPage(
        url=f"{_SOURCE_REPO}/blob/{ref}/packs/pf2e/{relative_path}",
        category=pack,
        title=entry["name"],
        source_book=publication.get("title") or None,
        traits=[str(t) for t in (_value_of(system, "traits") or [])],
        body="\n\n".join(parts),
        fetched_at="",
    )


def convert_tree(packs_root: Path, output_dir: Path, ref: str = DEFAULT_REF) -> dict[str, int]:
    """Convert every pack under *packs_root*, one .jsonl per pack.

    Returns entries written per pack. Packs that yield nothing are left out
    rather than written empty, so the result reads as a manifest.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, int] = {}

    for pack_dir in sorted(p for p in packs_root.iterdir() if p.is_dir()):
        pack = pack_dir.name
        if pack in EFFECT_PACKS:
            continue

        records: list[dict] = []
        for path in sorted(pack_dir.rglob("*.json")):
            if path.name.startswith("_"):
                continue
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                _log.warning("Skipping %s: %s", path, exc)
                continue

            relative_path = path.relative_to(packs_root).as_posix()
            # A journal carries several pages of prose; an item carries one
            # description. Which of the two this is decides how it is read.
            if isinstance(entry, dict) and isinstance(entry.get("pages"), list):
                pages = journal_to_pages(entry, pack=pack, relative_path=relative_path, ref=ref)
            else:
                page = entry_to_page(entry, pack=pack, relative_path=relative_path, ref=ref)
                pages = [page] if page is not None else []

            for page in pages:
                records.extend(asdict(chunk) for chunk in chunk_page(page, language="en"))

        if not records:
            continue

        out_path = output_dir / f"{pack}.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        written[pack] = len(records)
        _log.info("Wrote %d chunks to %s", len(records), out_path)

    return written
