"""Counts concrete entity models per family in `decomp/src` (one file, one
public class, per decomp's shape - see `hover_tips.py`).

This is a sizing reference for `build_vocab.ID_WIDTH`: `16**ID_WIDTH` must
exceed any single episode's entity count per namespace, not the game's total
roster (see docs/TOKENIZER.md "Open decisions"), so knowing the
current roster size per family is what an ID_WIDTH review actually checks
against.

Classes may extend a family's root model directly, or through intermediate
abstract subclasses never instantiated on their own (e.g. `AnticipatePower`
extends `TemporaryDexterityPower` extends `PowerModel`) - counting correctly
means walking the inheritance chain within the directory, not just matching
the root class name.

Usage: uv run python -m model.tokenizer.count_entities
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from model.tokenizer.loc_tables import REPO_ROOT

SRC_DIR = REPO_ROOT / "decomp" / "src"

# Directory (relative to SRC_DIR) -> (loc table name, root model class).
# These are exactly the families in loc_tables.REFERENCEABLE_TABLES, i.e.
# the ones whose entities get <REF_START> reference ID blocks.
MODEL_FAMILIES = {
    "MegaCrit.Sts2.Core.Models.Cards": ("cards", "CardModel"),
    "MegaCrit.Sts2.Core.Models.Relics": ("relics", "RelicModel"),
    "MegaCrit.Sts2.Core.Models.Powers": ("powers", "PowerModel"),
    "MegaCrit.Sts2.Core.Models.Potions": ("potions", "PotionModel"),
    "MegaCrit.Sts2.Core.Models.Monsters": ("monsters", "MonsterModel"),
    "MegaCrit.Sts2.Core.Models.Orbs": ("orbs", "OrbModel"),
    "MegaCrit.Sts2.Core.Models.Enchantments": ("enchantments", "EnchantmentModel"),
    "MegaCrit.Sts2.Core.Models.Afflictions": ("afflictions", "AfflictionModel"),
    "MegaCrit.Sts2.Core.Models.Events": ("events", "EventModel"),
    "MegaCrit.Sts2.Core.Models.Encounters": ("encounters", "EncounterModel"),
}

# Matches the one class declaration per decomp file, e.g.
# "public sealed class Aggression : CardModel" or
# "public sealed class Disintegration : CardModel, KnowledgeDemon.IChoosable"
# (trailing interfaces are ignored - only the first base token is captured).
_CLASS_RE = re.compile(
    r"^public\s+(?:(abstract)\s+|sealed\s+)?class\s+(\w+)\s*:\s*(\w+)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class FamilyCount:
    table: str
    concrete: int
    abstract_bases: int
    unresolved: tuple[str, ...]  # concrete classes whose base chain never reaches the root


def _parse_classes(directory: Path) -> dict[str, tuple[str, bool]]:
    """{class_name: (base_class_name, is_abstract)} for every class declared
    directly in `directory`."""
    classes: dict[str, tuple[str, bool]] = {}
    for path in directory.glob("*.cs"):
        match = _CLASS_RE.search(path.read_text(encoding="utf-8"))
        if match:
            is_abstract, name, base = match.groups()
            classes[name] = (base, is_abstract is not None)
    return classes


def count_family(directory: Path, root: str) -> FamilyCount:
    classes = _parse_classes(directory)
    concrete = 0
    abstract_bases = 0
    unresolved = []
    for name, (base, is_abstract) in classes.items():
        if is_abstract:
            abstract_bases += 1
            continue
        current = base
        seen = {name}
        while current != root and current in classes and current not in seen:
            seen.add(current)
            current = classes[current][0]
        if current == root:
            concrete += 1
        else:
            unresolved.append(name)
    return FamilyCount(
        table=directory.name,
        concrete=concrete,
        abstract_bases=abstract_bases,
        unresolved=tuple(sorted(unresolved)),
    )


def count_all_families() -> dict[str, FamilyCount]:
    results = {}
    for rel_dir, (table, root) in MODEL_FAMILIES.items():
        directory = SRC_DIR / rel_dir
        if directory.is_dir():
            results[table] = count_family(directory, root)
    return results


def main() -> None:
    for table, result in count_all_families().items():
        print(f"{table}: {result.concrete} concrete ({result.abstract_bases} abstract bases skipped)")
        if result.unresolved:
            print(f"  unresolved, not rooted in the family model: {', '.join(result.unresolved)}")


if __name__ == "__main__":
    main()
