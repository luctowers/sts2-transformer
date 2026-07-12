"""Mirrors MegaCrit.Sts2.Core.Models.Cards.StrikeIronclad (and its sibling
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


class Strike(CardModel):
    def __init__(self, damage: int = 6):
        super().__init__(cost=1, card_type=CardType.ATTACK, target_type=TargetType.ANY_ENEMY)
        self.damage = damage

    def on_play(self, state: "CombatState", card_play: "CardPlay") -> None:
        assert card_play.target is not None
        creature_cmd.damage(state, card_play.target, self.damage, dealer=self.owner.creature)
