"""Mirrors MegaCrit.Sts2.Core.Combat.CombatState.

Holds everything that represents the current combat: who's in it, whose
side is active, and the dispatch point through which every mutation must
pass (see engine/combat/events.py). Unlike the decomp, this is a plain
constructible object with no ties to a run/save/multiplayer - see
docs/ARCHITECTURE.md's simulator design constraints. `rng` and `history`
live here (rather than on CombatManager, as in the decomp) so that a
CombatState is a self-contained trajectory: construct one, drive it via
dispatch, and its `history` is the full replayable event stream.
"""

from __future__ import annotations

import random
from typing import List, Optional

from engine.combat.combat_history import CombatHistory
from engine.combat.combat_side import CombatSide
from engine.combat.events import Event
from engine.entities.creatures.creature import Creature
from engine.entities.players.player import Player


class CombatState:
    def __init__(self, player: Player, enemy: Creature, rng: Optional[random.Random] = None):
        self.allies: List[Creature] = [player.creature]
        self.enemies: List[Creature] = [enemy]
        self.player = player
        self.current_side = CombatSide.PLAYER
        self.round_number = 1
        self.rng = rng or random.Random()
        self.history = CombatHistory()

    @property
    def creatures(self) -> List[Creature]:
        return self.allies + self.enemies

    @property
    def is_over(self) -> bool:
        return self.player.creature.is_dead or self.enemies[0].is_dead

    @property
    def player_won(self) -> Optional[bool]:
        if not self.is_over:
            return None
        return self.enemies[0].is_dead

    def dispatch(self, event: Event) -> Event:
        """The only legal way to mutate combat state: stamp the event with
        the current turn context, apply its effect, and log it."""
        event.round_number = self.round_number
        event.side = self.current_side
        event.apply(self)
        self.history.add(event)
        return event
