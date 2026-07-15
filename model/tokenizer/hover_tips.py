"""Extracts each entity's expected-reference list from its `ExtraHoverTips`
declaration in the decompiled C# source (see docs/TOKENIZER.md "Reference
substitution details").

This is a best-effort scrape, not a C# parser: decompiled model files have a
very uniform shape (one public class per file, entry ID = Slugify(class
name) - see MegaCrit.Sts2.Core.Models.ModelDb.GetEntry /
MegaCrit.Sts2.Core.Helpers.StringHelper.Slugify), so regex extraction is
reliable enough to cross-check the reference lexicon against, which is all
this is used for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from model.tokenizer.loc_tables import REPO_ROOT

SRC_DIR = REPO_ROOT / "decomp" / "src"

# Directory (relative to SRC_DIR) -> loc table its classes belong to.
MODEL_DIRS = {
    "MegaCrit.Sts2.Core.Models.Cards": "cards",
    "MegaCrit.Sts2.Core.Models.Relics": "relics",
    "MegaCrit.Sts2.Core.Models.Powers": "powers",
    "MegaCrit.Sts2.Core.Models.Potions": "potions",
    "MegaCrit.Sts2.Core.Models.Orbs": "orbs",
    "MegaCrit.Sts2.Core.Models.Afflictions": "afflictions",
    "MegaCrit.Sts2.Core.Models.Enchantments": "enchantments",
}

# HoverTipFactory.From<Family><Suffix?><TGeneric>(...) -> loc table.
_FACTORY_FAMILY_TO_TABLE = {
    "Card": "cards",
    "Power": "powers",
    "Relic": "relics",
    "Potion": "potions",
    "Orb": "orbs",
    "Affliction": "afflictions",
    "Enchantment": "enchantments",
}

_HOVER_TIP_REF_RE = re.compile(
    r"HoverTipFactory\.From(Card|Power|Relic|Potion|Orb|Affliction|Enchantment)"
    r"(?:WithCardHoverTips|WithPowerHoverTips|ExcludingItself)?<(\w+)>"
)

# HoverTipFactory.FromForge() is hardcoded in HoverTipFactory itself to also
# tip Sovereign Blade (see docs/TOKENIZER.md) - not visible from a per-model
# regex scan, so it's special-cased here.
_FROM_FORGE_RE = re.compile(r"HoverTipFactory\.FromForge\(\)")
_FROM_FORGE_EXPANSION = ("cards", "SovereignBlade")


def slugify_class_name(name: str) -> str:
    """Python port of MegaCrit.Sts2.Core.Helpers.StringHelper.Slugify,
    restricted to plain PascalCase class names (no whitespace/punctuation to
    strip, unlike the general-purpose original)."""
    return re.sub(r"(?<=[A-Za-z0-9])(?=[A-Z])", "_", name).upper()


def _extract_property_body(text: str, prop_name: str) -> str | None:
    idx = text.find(prop_name)
    if idx == -1:
        return None
    start = idx + len(prop_name)
    depth = 0
    started = False
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in "{(":
            depth += 1
            started = True
        elif ch in "})":
            depth -= 1
        if started and depth == 0:
            # Consume a trailing ';' for expression-bodied properties.
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            end = j + 1 if j < n and text[j] == ";" else i + 1
            return text[start:end]
        i += 1
    return None


@dataclass(frozen=True)
class ExpectedReference:
    table: str
    entry_id: str


def _references_in_body(body: str) -> list[ExpectedReference]:
    refs = []
    for family, generic_arg in _HOVER_TIP_REF_RE.findall(body):
        table = _FACTORY_FAMILY_TO_TABLE[family]
        refs.append(ExpectedReference(table, slugify_class_name(generic_arg)))
    if _FROM_FORGE_RE.search(body):
        table, class_name = _FROM_FORGE_EXPANSION
        refs.append(ExpectedReference(table, slugify_class_name(class_name)))
    return refs


def build_expected_references() -> dict[tuple[str, str], list[ExpectedReference]]:
    """Returns {(table, entry_id): [ExpectedReference, ...]} for every model
    file that declares `ExtraHoverTips`, plus an implicit self-reference for
    every entity (cards never declare a tip for their own title)."""
    expected: dict[tuple[str, str], list[ExpectedReference]] = {}
    for rel_dir, table in MODEL_DIRS.items():
        directory = SRC_DIR / rel_dir
        if not directory.is_dir():
            continue
        for path in directory.glob("*.cs"):
            class_name = path.stem
            entry_id = slugify_class_name(class_name)
            text = path.read_text(encoding="utf-8")
            body = _extract_property_body(text, "ExtraHoverTips")
            refs = _references_in_body(body) if body else []
            refs.append(ExpectedReference(table, entry_id))  # self-reference
            expected[(table, entry_id)] = refs
    return expected
