"""Mirrors MegaCrit.Sts2.Core.Entities.Cards.CardPile.

Simplified: no events, no mod/hook subscription bookkeeping. Cards are
plain Python objects added/removed from a list.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, List

from engine.entities.cards.pile_type import PileType

if TYPE_CHECKING:
    from engine.models.card_model import CardModel


class CardPile:
    def __init__(self, pile_type: PileType):
        self.type = pile_type
        self.cards: List["CardModel"] = []

    @property
    def is_empty(self) -> bool:
        return not self.cards

    def add(self, card: "CardModel", index: int | None = None) -> None:
        if index is None:
            self.cards.append(card)
        else:
            self.cards.insert(index, card)

    def remove(self, card: "CardModel") -> None:
        self.cards.remove(card)

    def clear(self) -> List["CardModel"]:
        cards, self.cards = self.cards, []
        return cards

    def shuffle(self, rng: random.Random) -> None:
        rng.shuffle(self.cards)
