"""Mirrors MegaCrit.Sts2.Core.Commands.CreatureCmd (Damage/GainBlock subset).

Cards call these instead of mutating a Creature or dispatching events
themselves. Every function here only ever builds an Event and hands it to
CombatState.dispatch - it never touches a Creature's fields itself. See
engine/combat/events.py for why that split matters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.combat.events import BlockGained, DamageDealt
from engine.entities.creatures.creature import Creature

if TYPE_CHECKING:
    from engine.combat.combat_state import CombatState


def damage(state: "CombatState", target: Creature, amount: int, dealer: Optional[Creature] = None) -> DamageDealt:
    return state.dispatch(DamageDealt(target=target, amount=amount, dealer=dealer))


def gain_block(state: "CombatState", creature: Creature, amount: int) -> BlockGained:
    return state.dispatch(BlockGained(creature=creature, amount=amount))
