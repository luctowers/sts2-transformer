"""Mirrors MegaCrit.Sts2.Core.Entities.Cards.PileType.

Only Draw/Hand/Discard/Play are actually used by the current turn flow (no
card in this narrow scope exhausts), but Exhaust and Deck are kept in the
enum for structural parity with the decomp, since future card ports will
need them.
"""

from __future__ import annotations

from enum import Enum, auto


class PileType(Enum):
    DRAW = auto()
    HAND = auto()
    DISCARD = auto()
    EXHAUST = auto()
    PLAY = auto()
    DECK = auto()
