"""Mirrors MegaCrit.Sts2.Core.Entities.Intents (Attack/None subset).

The real game has many intent types (attack, buff, debuff, defend, escape,
...). This scope only needs to distinguish "will attack" from "will do
nothing".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class IntentType(Enum):
    ATTACK = auto()
    NONE = auto()


@dataclass(frozen=True)
class Intent:
    type: IntentType
    damage: int = 0
