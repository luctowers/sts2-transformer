"""Builds the frozen tokenizer artifacts from decomp/.

Single entry point, no parameters: the output must be a pure function of
decomp/ plus this script (see docs/TOKENIZER.md "Vocab build"), so any rebuild is
bit-identical and CI can rebuild-and-compare. Run it after regenerating
decomp/ (a game update) to pick up new mechanics words - this is a reviewed,
versioned diff, since it shifts token IDs and invalidates trained
checkpoints.

Usage: uv run python -m model.tokenizer.build_vocab
"""

from __future__ import annotations

import hashlib
import json

from model.tokenizer import hover_tips, loc_tables, text_template
from model.tokenizer.reference_lexicon import ReferenceMatcher, build_reference_lexicon

OUT_DIR = loc_tables.REPO_ROOT / "model" / "tokenizer"

# ID_WIDTH: how many base-16 digits follow a reference marker, i.e. how many
# distinct entities per namespace a single episode can hold (16**ID_WIDTH).
# See docs/TOKENIZER.md "The scheme" and "Open decisions". Widening this adds
# zero vocab tokens - it only changes sequence shape - but it's still a
# reviewed constant change that invalidates trained checkpoints (input
# format change). 3 (4096 slots/namespace) covers the largest per-episode
# roster (cards) with comfortable headroom; see count_entities.py.
ID_WIDTH = 3

SPECIAL_TOKENS = ["<PAD>", "<UNK>"]
DIGIT_TOKENS = [str(d) for d in range(10)]
# <ENERGY> is called out explicitly in docs/TOKENIZER.md; <STAR> is the same
# glyph-token treatment extended to starIcons()/singleStarIcon, which render
# just as consistently to a single fixed icon regardless of repeat count.
# ".", "," and ":" carry real clause/sentence-boundary structure, so they're
# kept as tokens rather than stripped like purely decorative punctuation
# (quotes, parens) - see text_template.py's _SYMBOL_CHAR_RE. "X" is the
# game's placeholder for a value determined elsewhere ("Deal X damage"), kept
# capitalized and distinct from the ordinary lowercase "x" multiplier suffix
# ("2x" the damage) - see text_template.py's _X_VAR_RE.
SYMBOL_TOKENS = ["<ENERGY>", "<STAR>", "+", "%", ".", ",", ":", "X"]

# Fixed like the specials above, not derived from decomp/ - opens every
# reference ID block regardless of namespace (docs/TOKENIZER.md "The
# scheme"). The namespace itself is tagged by the referenceable table's own
# name ("cards", "orbs", ...), reusing the ordinary mechanics word rather
# than a dedicated per-namespace marker - see the namespace-word check in
# compute() below, which guarantees that reuse is safe.
REF_START_TOKEN = "<REF_START>"
_HEX_DIGITS = "0123456789ABCDEF"
# Base-16 identity digits, disjoint from the text digits above: ID digits are
# meaning-free identity re-randomized every episode, text digits carry
# magnitude - sharing rows would inject identity noise into number semantics.
ID_DIGIT_TOKENS = [f"<ID_{h}>" for h in _HEX_DIGITS]


def _entity_raw_text(entry_fields: dict[str, str], fields: tuple[str, ...]) -> str:
    return "\n".join(entry_fields[f] for f in fields if entry_fields.get(f))


def _scan_mechanics_words(matcher: ReferenceMatcher) -> tuple[set[str], list[str]]:
    words: set[str] = set()
    unrecognized: list[str] = []
    for table, fields in loc_tables.DESCRIPTION_FIELDS.items():
        entries = loc_tables.entries_for_table(table)
        for entry_fields in entries.values():
            for field in fields:
                raw = entry_fields.get(field)
                if raw:
                    text_template.collect_words(raw, words, unrecognized, matcher.substitute)
    return words, unrecognized


def _cross_check_hover_tips(matcher: ReferenceMatcher) -> list[str]:
    """Cross-checks the reference lexicon's matches against hover-tip
    declarations in decomp/src, in both directions (docs/TOKENIZER.md
    "Reference substitution details"). Returns human-readable warnings for
    manual review; never raises, since the scrape is best-effort."""
    warnings: list[str] = []
    expected = hover_tips.build_expected_references()
    for table, fields in loc_tables.DESCRIPTION_FIELDS.items():
        if table not in ("cards", "relics", "powers", "potions"):
            continue  # only these tables' entities declare ExtraHoverTips
        entries = loc_tables.entries_for_table(table)
        for entry_id, entry_fields in entries.items():
            raw_text = _entity_raw_text(entry_fields, fields)
            if not raw_text:
                continue
            matched = matcher.find_all(raw_text)
            declared = expected.get((table, entry_id))
            if declared is None:
                continue  # no ExtraHoverTips override found for this entity
            declared_set = {(r.table, r.entry_id) for r in declared}
            for ref in matched:
                key = (ref.table, ref.entry_id)
                if key not in declared_set:
                    warnings.append(
                        f"{table}.{entry_id}: text references {ref.table}.{ref.entry_id} "
                        "with no corresponding hover tip"
                    )
            for ref in declared:
                key = (ref.table, ref.entry_id)
                if key == (table, entry_id):
                    continue  # self-reference isn't required to appear literally
                if ref.table not in loc_tables.REFERENCEABLE_TABLES:
                    continue  # e.g. enchantments aren't a referenceable table, can't match
                if key not in {(m.table, m.entry_id) for m in matched}:
                    warnings.append(
                        f"{table}.{entry_id}: declares a hover tip for "
                        f"{ref.table}.{ref.entry_id} that never matches in its text"
                    )
    return warnings


def compute() -> dict:
    """Pure function of decomp/ (plus this module): {vocab, lexicon_json,
    expected_references_json, warnings}. Split out from build() so tests can
    rebuild in-memory and compare against the checked-in artifacts without
    touching disk."""
    lexicon = build_reference_lexicon()
    matcher = ReferenceMatcher(lexicon)

    words, unrecognized = _scan_mechanics_words(matcher)

    # <REF_START> blocks reuse each referenceable table's own name as its
    # namespace tag (docs/TOKENIZER.md "The scheme"), so every one of them
    # must actually occur as ordinary text somewhere in the game's
    # descriptions - fail loudly at build time rather than let the runtime
    # silently emit <UNK> for a reference's namespace word.
    missing_namespace_words = [t for t in loc_tables.REFERENCEABLE_TABLES if t not in words]
    if missing_namespace_words:
        raise ValueError(
            "reference namespace word(s) missing from the mechanics vocab: "
            f"{missing_namespace_words}"
        )

    warnings = []
    if unrecognized:
        warnings.append(f"{len(unrecognized)} unrecognized placeholder pattern(s):")
        warnings.extend(f"  {{{body}}}" for body in sorted(set(unrecognized)))
    warnings.extend(_cross_check_hover_tips(matcher))

    tokens = (
        SPECIAL_TOKENS
        + DIGIT_TOKENS
        + SYMBOL_TOKENS
        + [REF_START_TOKEN]
        + ID_DIGIT_TOKENS
        + sorted(words)
    )
    content_hash = hashlib.sha256(json.dumps(tokens).encode("utf-8")).hexdigest()

    vocab = {
        "game_version": loc_tables.source_version(),
        "content_hash": content_hash,
        "id_width": ID_WIDTH,
        "specials": SPECIAL_TOKENS,
        "digits": DIGIT_TOKENS,
        "symbols": SYMBOL_TOKENS,
        "ref_start": REF_START_TOKEN,
        "id_digits": ID_DIGIT_TOKENS,
        "tokens": tokens,
    }

    lexicon_json = {
        surface: {"table": ref.table, "entry_id": ref.entry_id, "upgraded": ref.upgraded}
        for surface, ref in sorted(lexicon.items())
    }

    expected = hover_tips.build_expected_references()
    expected_json = {
        f"{table}.{entry_id}": [f"{r.table}.{r.entry_id}" for r in refs]
        for (table, entry_id), refs in sorted(expected.items())
    }

    return {
        "vocab": vocab,
        "lexicon_json": lexicon_json,
        "expected_references_json": expected_json,
        "warnings": warnings,
    }


def build() -> None:
    result = compute()

    for warning in result["warnings"]:
        print(f"WARNING: {warning}")

    (OUT_DIR / "vocab.json").write_text(
        json.dumps(result["vocab"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "reference_lexicon.json").write_text(
        json.dumps(result["lexicon_json"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "expected_references.json").write_text(
        json.dumps(result["expected_references_json"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    tokens = result["vocab"]["tokens"]
    print(f"Wrote {len(tokens)} tokens to vocab.json")


if __name__ == "__main__":
    build()
