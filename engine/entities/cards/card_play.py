"""Mirrors MegaCrit.Sts2.Core.Entities.Cards.CardPlay.

The real CardPlay carries a lot of context needed for hooks (energy spent,
star cost, etc). Here it's just the card and its resolved target, which is
all CardModel.on_play needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from engine.entities.creatures.creature import Creature
    from engine.models.card_model import CardModel


@dataclass(frozen=True)
class CardPlay:
    card: "CardModel"
    target: Optional["Creature"]
