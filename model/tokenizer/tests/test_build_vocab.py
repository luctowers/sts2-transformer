"""OOV sweep (docs/TOKENIZER.md "Testing"): every description in every
table, all branches expanded, must tokenize with zero <UNK>. Enforced here as
"a fresh rebuild from decomp/ exactly matches the checked-in vocab.json" -
if decomp/ has been regenerated (new mechanics words) without rebuilding
the vocab, this fails, which is the OOV sweep's CI requirement.
"""

from __future__ import annotations

import json

from model.tokenizer import build_vocab
from model.tokenizer.loc_tables import REPO_ROOT

TOKENIZER_DIR = REPO_ROOT / "model" / "tokenizer"


def _load(name: str) -> dict:
    with (TOKENIZER_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def test_no_unrecognized_placeholder_patterns():
    result = build_vocab.compute()
    unrecognized = [w for w in result["warnings"] if "unrecognized placeholder" in w]
    assert not unrecognized, "\n".join(unrecognized)


def test_checked_in_vocab_matches_fresh_rebuild():
    checked_in = _load("vocab.json")
    fresh = build_vocab.compute()["vocab"]

    assert fresh["content_hash"] == checked_in["content_hash"], (
        "decomp/ has been regenerated without rebuilding the vocab - "
        "run `uv run python -m model.tokenizer.build_vocab` and commit the diff"
    )
    assert fresh["tokens"] == checked_in["tokens"]


def test_checked_in_reference_lexicon_matches_fresh_rebuild():
    checked_in = _load("reference_lexicon.json")
    fresh = build_vocab.compute()["lexicon_json"]
    assert fresh == checked_in


def test_vocab_has_no_duplicate_tokens():
    vocab = _load("vocab.json")
    tokens = vocab["tokens"]
    assert len(tokens) == len(set(tokens))


def test_reference_and_digit_and_symbol_tokens_never_collide_with_words():
    vocab = _load("vocab.json")
    words = (
        set(vocab["tokens"])
        - set(vocab["specials"])
        - set(vocab["digits"])
        - set(vocab["symbols"])
        - set(vocab["id_digits"])
        - {vocab["ref_start"]}
    )
    # Every remaining token should be a plain lowercase mechanics word -
    # including each referenceable table's own name (e.g. "cards", "orbs"),
    # which <REF_START> blocks reuse as their namespace tag.
    assert all(w.islower() and "_" not in w for w in words), sorted(
        w for w in words if not (w.islower() and "_" not in w)
    )
