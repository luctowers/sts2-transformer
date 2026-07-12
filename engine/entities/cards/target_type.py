"""Mirrors MegaCrit.Sts2.Core.Entities.Cards.TargetType (Self/AnyEnemy subset)."""

from __future__ import annotations

from enum import Enum, auto


class TargetType(Enum):
    SELF = auto()
    ANY_ENEMY = auto()
