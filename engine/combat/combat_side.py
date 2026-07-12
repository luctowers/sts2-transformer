"""Mirrors MegaCrit.Sts2.Core.Combat.CombatSide."""

from __future__ import annotations

from enum import Enum, auto


class CombatSide(Enum):
    PLAYER = auto()
    ENEMY = auto()

    def opposite(self) -> "CombatSide":
        return CombatSide.ENEMY if self is CombatSide.PLAYER else CombatSide.PLAYER
