"""Loads the game's English localization tables (see docs/DECOMP.md).

Every table under decomp/pck/localization/eng/ is a flat JSON object mapping
"ENTRY_ID.field" (or "ENTRY_ID.moves.MOVE_ID.field" for monsters) to a
string. This module reshapes that into a nested {entry_id: {field: text}}
dict per table.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
LOC_DIR = REPO_ROOT / "decomp" / "pck" / "localization" / "eng"
SOURCE_VERSION_PATH = REPO_ROOT / "decomp" / "SOURCE_VERSION.json"

# Description-like fields to scan for vocab, per table. Flavor/narrative
# fields (flavor, approval, warning, banter, dialogue, historyEntry, ...)
# are deliberately excluded.
DESCRIPTION_FIELDS: Mapping[str, tuple[str, ...]] = {
    "cards": ("description", "selectionScreenPrompt", "discardSelectionPrompt"),
    "card_keywords": ("description",),
    "relics": (
        "description",
        "eventDescription",
        "selectionScreenPrompt",
        "additionalRestSiteHealText",
        "infoText",
    ),
    "powers": (
        "description",
        "smartDescription",
        "remoteDescription",
        "selectionScreenPrompt",
        "infiniteAutoPlayCapReached",
    ),
    "potions": ("description", "selectionScreenPrompt"),
    "orbs": ("description", "smartDescription"),
    "afflictions": ("description", "extraCardText"),
    "enchantments": ("description", "extraCardText"),
    "modifiers": ("description", "selectionPrompt", "additionalRestSiteHealText"),
    "intents": ("description",),
}

# Tables whose entities can be referenced from other entities' descriptions -
# every titled entity table. Each table's own name doubles as the namespace
# tag in its <REF_START> blocks (docs/TOKENIZER.md "The scheme"). Most names
# occur literally in ordinary game text; those that never do (e.g.
# "enchantments", whose only literal form is the singular "enchantment") are
# added as tag-only vocab words by build_vocab.
#
# Order is a collision priority: when two tables share a title surface form
# (e.g. both a monster "Axebot" and the "Axebot" encounter named after it), the
# LATER table wins that form in the lexicon (see build_reference_lexicon). So
# "encounters" comes first, giving it the lowest priority: its titles are just
# its constituent monsters' names or combat-group labels, so a bare "Axebot" in
# prose must resolve to the monster, never the encounter. Encounters still get
# their own namespace (for the entity's prepend tag) and win the ~40 titles
# that are genuinely encounter-only ("Cultists", "Group of Slimes", ...).
REFERENCEABLE_TABLES = (
    "encounters",
    "cards",
    "relics",
    "powers",
    "potions",
    "monsters",
    "orbs",
    "enchantments",
    "afflictions",
    "events",
)


def load_table(table: str) -> dict[str, str]:
    path = LOC_DIR / f"{table}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def entries_for_table(table: str) -> dict[str, dict[str, str]]:
    """Reshape a flat loc table into {entry_id: {field: text}}.

    For monsters.json, "ENTRY.moves.MOVE.field" keys are kept out of the
    per-entry field dict (moves are not entities with slots); only the
    "ENTRY.name" key becomes the entry's title-equivalent field "title".
    """
    flat = load_table(table)
    entries: dict[str, dict[str, str]] = {}
    for key, value in flat.items():
        entry_id, _, field = key.partition(".")
        if not field or "." in field:
            continue
        if table == "monsters" and field == "moves":
            continue
        if table == "monsters" and field == "name":
            field = "title"
        entries.setdefault(entry_id, {})[field] = value
    return entries


def titles_for_table(table: str) -> dict[str, str]:
    return {
        entry_id: fields["title"]
        for entry_id, fields in entries_for_table(table).items()
        if "title" in fields
    }


def source_version() -> dict[str, str]:
    with SOURCE_VERSION_PATH.open(encoding="utf-8") as f:
        return json.load(f)
