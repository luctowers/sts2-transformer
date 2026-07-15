"""Substitution goldens and the permutation test from docs/TOKENIZER.md
"Testing": plural references (Blade Dance), nested plural+upgrade branches
(Charge), unmarked references (Claw), multi-word titles (Sovereign
Blade/Minion Strike), sentence-structure punctuation kept as symbol tokens
(Afterimage's comma, periods throughout).

These use hand-written "already rendered" text (concrete numbers picked,
one SmartFormat branch chosen, markup still present) standing in for what
the sim's renderer will eventually produce - rendering itself is out of
scope here (see docs/TOKENIZER.md pipeline step 1).
"""

from __future__ import annotations

import pytest

from model.tokenizer.loc_tables import REPO_ROOT
from model.tokenizer.tokenizer import UNK, Tokenizer

VOCAB_PATH = REPO_ROOT / "model" / "tokenizer" / "vocab.json"


@pytest.fixture(scope="module")
def tokenizer() -> Tokenizer:
    return Tokenizer(VOCAB_PATH)


def _block(tokenizer: Tokenizer, entity_key: str, ordinal: int) -> str:
    """The decoded `<REF:cards:004>`-style span for an assignment entry."""
    table = entity_key.split(".")[0]
    return f"<REF:{table}:{ordinal:0{tokenizer.id_width}X}>"


def _decoded(tokenizer: Tokenizer, text: str, assignment: dict[str, int]) -> str:
    ids = tokenizer.tokenize(text, assignment)
    assert tokenizer.unk_id not in ids, f"<UNK> in {tokenizer.decode(ids)!r}"
    return tokenizer.decode(ids)


def test_blade_dance_plural_reference(tokenizer):
    # BLADE_DANCE.description, Cards=3 (plural branch: Shiv -> Shivs).
    text = "Add 3 [gold]Shivs[/gold] into your [gold]Hand[/gold]."
    decoded = _decoded(tokenizer, text, {"cards.SHIV": 4})
    assert decoded == f"add 3 {_block(tokenizer, 'cards.SHIV', 4)} into your hand ."


def test_comma_kept_as_symbol_token(tokenizer):
    # AFTERIMAGE.description - clause-separating comma, not decorative.
    text = "Whenever you play a card, gain 1 [gold]Block[/gold]."
    decoded = _decoded(tokenizer, text, {})
    assert decoded == "whenever you play a card , gain 1 block ."


def test_claw_unmarked_reference(tokenizer):
    # CLAW.description - "ALL Claw cards" has no [gold] markup at all.
    text = "Deal 6 damage.\nIncrease the damage of ALL Claw cards by 3 this combat."
    decoded = _decoded(tokenizer, text, {"cards.CLAW": 0})
    assert decoded == (
        f"deal 6 damage . increase the damage of all {_block(tokenizer, 'cards.CLAW', 0)} "
        "cards by 3 this combat ."
    )


def test_minion_strike_multiword_upgraded_reference(tokenizer):
    # BEGONE.description - multi-word title with an upgraded "+" marker.
    text = "Choose a card in your [gold]Hand[/gold] to [gold]Transform[/gold] into [gold]Minion Strike+[/gold]."
    decoded = _decoded(tokenizer, text, {"cards.MINION_STRIKE": 9})
    assert f"{_block(tokenizer, 'cards.MINION_STRIKE', 9)} +" in decoded
    assert "minion" not in decoded and "strike" not in decoded


def test_charge_nested_plural_and_upgrade(tokenizer):
    # CHARGE.description - a plural branch whose own branches are
    # themselves an IfUpgraded:show, so all four surface forms must resolve
    # to the same reference ID block.
    cases = [
        ("Minion Dive Bomb", False),
        ("Minion Dive Bomb+", True),
        ("Minion Dive Bombs", False),
        ("Minion Dive Bombs+", True),
    ]
    for surface, upgraded in cases:
        text = f"Choose 1 card in your [gold]Draw Pile[/gold] to [gold]Transform[/gold] into [gold]{surface}[/gold]."
        decoded = _decoded(tokenizer, text, {"cards.MINION_DIVE_BOMB": 2})
        block = _block(tokenizer, "cards.MINION_DIVE_BOMB", 2)
        expected = f"{block} +" if upgraded else block
        assert expected in decoded, (surface, decoded)


def test_permutation_invariance(tokenizer):
    """Tokenizing the same text under two different ordinal assignments must
    yield identical streams up to remapping the ID digit blocks (a block is
    remapped as a unit, not digit-by-digit)."""
    text = "Deal 6 damage.\nIncrease the damage of ALL Claw cards by 3 this combat. Add 3 Shivs into your Hand."
    assignment_a = {"cards.CLAW": 0, "cards.SHIV": 1}
    assignment_b = {"cards.CLAW": 7, "cards.SHIV": 2}

    decoded_a = _decoded(tokenizer, text, assignment_a)
    decoded_b = _decoded(tokenizer, text, assignment_b)

    def relabel(decoded: str, assignment: dict[str, int]) -> str:
        for entity_key, ordinal in assignment.items():
            decoded = decoded.replace(_block(tokenizer, entity_key, ordinal), entity_key)
        return decoded

    assert relabel(decoded_a, assignment_a) == relabel(decoded_b, assignment_b)


def test_unk_never_occurs_for_bare_mechanics_text(tokenizer):
    text = "Gain 3 Block. Draw 2 cards. Exhaust this card."
    decoded = _decoded(tokenizer, text, {})
    assert UNK not in decoded


def test_ordinal_out_of_range_rejected(tokenizer):
    # ID_WIDTH=3 caps ordinals at 16**3=4096 (docs/TOKENIZER.md "Testing" -
    # "Range check").
    text = "Deal 6 damage.\nIncrease the damage of ALL Claw cards by 3 this combat."
    with pytest.raises(ValueError):
        tokenizer.tokenize(text, {"cards.CLAW": 4096})


def test_x_var_distinct_from_x_multiplier_suffix(tokenizer):
    # SKEWER.description's "X" (an amount determined elsewhere) must not
    # collapse into REFLECTIVE_FORTRESS_POWER.smartDescription's literal "x"
    # multiplier suffix ("2x" the blocked damage) - docs/TOKENIZER.md
    # "Symbols".
    x_var = _decoded(tokenizer, "Deal 6 damage X times.", {})
    assert x_var == "deal 6 damage X times ."

    x_suffix = _decoded(tokenizer, "2x the blocked damage is reflected.", {})
    assert x_suffix == "2 x the blocked damage is reflected ."

    assert "X" not in x_suffix
    assert "x" not in x_var.split()
