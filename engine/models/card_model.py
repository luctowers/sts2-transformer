"""Mirrors MegaCrit.Sts2.Core.Models.CardModel.

Simplified to a cost, a type, a target type, and an on_play effect. No
upgrades, keywords, dynamic vars, or enchantments in this scope, so unlike
the decomp there's no canonical/mutable split - a CardModel instance is
directly playable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from engine.combat.combat_side import CombatSide
from engine.entities.cards.card_type import CardType
from engine.entities.cards.target_type import TargetType

if TYPE_CHECKING:
    from engine.combat.combat_state import CombatState
    from engine.entities.cards.card_play import CardPlay
    from engine.entities.creatures.creature import Creature
    from engine.entities.players.player import Player


class CardModel(ABC):
    def __init__(self, cost: int, card_type: CardType, target_type: TargetType):
        self.cost = cost
        self.card_type = card_type
        self.target_type = target_type
        self.owner: Optional["Player"] = None

    def is_valid_target(self, target: Optional["Creature"]) -> bool:
        if self.target_type == TargetType.SELF:
            return target is None
        if self.target_type == TargetType.ANY_ENEMY:
            return target is not None and target.side == CombatSide.ENEMY and target.is_alive
        raise ValueError(f"Unhandled target type {self.target_type}")

    @abstractmethod
    def on_play(self, state: "CombatState", card_play: "CardPlay") -> None:
        ...
