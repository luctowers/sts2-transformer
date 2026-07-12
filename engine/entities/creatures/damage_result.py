"""Mirrors MegaCrit.Sts2.Core.Entities.Creatures.DamageResult."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.entities.creatures.creature import Creature


@dataclass
class DamageResult:
    receiver: "Creature"
    unblocked_damage: int = 0
    blocked_damage: int = 0
    was_target_killed: bool = False
    was_block_broken: bool = False
    was_fully_blocked: bool = False
