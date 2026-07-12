"""A representative starting deck for this narrow scope: 5 Strikes, 4 Defends
(the real Ironclad starting deck, minus the out-of-scope Bash)."""

from __future__ import annotations

from typing import List

from engine.models.card_model import CardModel
from engine.models.cards.defend import Defend
from engine.models.cards.strike import Strike


def starting_deck() -> List[CardModel]:
    return [Strike() for _ in range(5)] + [Defend() for _ in range(4)]
