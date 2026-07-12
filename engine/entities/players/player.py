"""Mirrors MegaCrit.Sts2.Core.Entities.Players.Player.

Simplified to what a relic-less, potion-less, single-player combat needs:
a Creature, an energy budget, and a deck. No gold/relics/potions/RunState.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from engine.combat.combat_side import CombatSide
from engine.entities.creatures.creature import Creature
from engine.entities.players.player_combat_state import PlayerCombatState

if TYPE_CHECKING:
    from engine.models.card_model import CardModel


class Player:
    def __init__(self, max_hp: int, max_energy: int, deck: List["CardModel"]):
        self.creature = Creature(side=CombatSide.PLAYER, current_hp=max_hp, max_hp=max_hp, player=self)
        self.max_energy = max_energy
        self.deck = deck
        for card in self.deck:
            card.owner = self
        self.combat_state: Optional[PlayerCombatState] = None

    def reset_combat_state(self) -> None:
        self.combat_state = PlayerCombatState(self)

    def populate_combat_state(self) -> None:
        """Moves the deck into the draw pile, unshuffled (the caller shuffles)."""
        for card in self.deck:
            self.combat_state.draw_pile.add(card)
