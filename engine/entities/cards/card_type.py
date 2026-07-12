"""Mirrors MegaCrit.Sts2.Core.Entities.Cards.CardType (Attack/Skill subset)."""

from __future__ import annotations

from enum import Enum, auto


class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
