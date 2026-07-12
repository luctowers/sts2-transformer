"""Mirrors MegaCrit.Sts2.Core.Models.Cards.DefendIronclad (and its sibling
Strike*/Defend* cards, which differ only in cosmetics in the real game)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.commands import creature_cmd
from engine.entities.cards.card_type import CardType
from engine.entities.cards.target_type import TargetType
from engine.models.card_model import CardModel

if TYPE_CHECKING:
    from engine.combat.combat_state import CombatState
    from engine.entities.cards.card_play import CardPlay


class Defend(CardModel):
    def __init__(self, block: int = 5):
        super().__init__(cost=1, card_type=CardType.SKILL, target_type=TargetType.SELF)
        self.block = block

    def on_play(self, state: "CombatState", card_play: "CardPlay") -> None:
        creature_cmd.gain_block(state, self.owner.creature, self.block)
