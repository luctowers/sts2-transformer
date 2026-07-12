"""Mirrors MegaCrit.Sts2.Core.Entities.Players.PlayerCombatState.

Holds the per-combat piles, energy, and turn number. No orb queue,
star cost, or hand-size cap beyond what's needed here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from engine.entities.cards.card_pile import CardPile
from engine.entities.cards.pile_type import PileType

if TYPE_CHECKING:
    from engine.entities.players.player import Player

MAX_CARDS_IN_HAND = 10


class PlayerCombatState:
    def __init__(self, player: "Player"):
        self.player = player
        self.hand = CardPile(PileType.HAND)
        self.draw_pile = CardPile(PileType.DRAW)
        self.discard_pile = CardPile(PileType.DISCARD)
        self.exhaust_pile = CardPile(PileType.EXHAUST)
        self.play_pile = CardPile(PileType.PLAY)
        self.energy = 0
        self.turn_number = 1

    @property
    def all_piles(self) -> List[CardPile]:
        return [self.hand, self.draw_pile, self.discard_pile, self.exhaust_pile, self.play_pile]

    def get_pile(self, pile_type: PileType) -> CardPile:
        for pile in self.all_piles:
            if pile.type == pile_type:
                return pile
        raise ValueError(f"No combat pile of type {pile_type}.")

    def increment_turn_number(self) -> None:
        self.turn_number += 1
