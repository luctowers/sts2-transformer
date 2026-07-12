"""Mirrors MegaCrit.Sts2.Core.Entities.Creatures.Creature.

A Creature is either a player's or a monster's body in combat: current/max
HP and block, plus a back-reference to whichever of Player/MonsterModel
owns it (exactly one of the two is set, mirroring the decomp's two
constructors). No powers/buffs/debuffs in this scope.

The `*_internal` methods mirror the decomp naming convention: they mutate
raw state directly. In the real game, Commands sit between game logic and
these methods so that Hooks (powers, relics) can intercept the values.
There are no hooks here, but keeping the split makes it obvious where a
future hook layer would plug in.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from engine.combat.combat_side import CombatSide
from engine.entities.creatures.damage_result import DamageResult

if TYPE_CHECKING:
    from engine.entities.players.player import Player
    from engine.models.monster_model import MonsterModel


class Creature:
    def __init__(
        self,
        *,
        side: CombatSide,
        current_hp: int,
        max_hp: int,
        player: Optional["Player"] = None,
        monster: Optional["MonsterModel"] = None,
    ):
        if (player is None) == (monster is None):
            raise ValueError("Creature must have exactly one of player or monster.")
        self.player = player
        self.monster = monster
        self.side = side
        self.current_hp = current_hp
        self.max_hp = max_hp
        self.block = 0

    @property
    def is_player(self) -> bool:
        return self.player is not None

    @property
    def is_monster(self) -> bool:
        return self.monster is not None

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def is_dead(self) -> bool:
        return not self.is_alive

    def gain_block_internal(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative.")
        self.block += amount

    def lose_block_internal(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative.")
        self.block = max(self.block - amount, 0)

    def damage_block_internal(self, amount: int) -> int:
        """Absorb `amount` damage with block. Returns how much was blocked."""
        blocked = min(self.block, amount)
        self.block -= blocked
        return blocked

    def lose_hp_internal(self, amount: int) -> DamageResult:
        was_killed = self.current_hp > 0 and amount >= self.current_hp
        hp_before = self.current_hp
        self.current_hp = max(self.current_hp - max(amount, 0), 0)
        return DamageResult(
            receiver=self,
            unblocked_damage=hp_before - self.current_hp,
            was_target_killed=was_killed,
        )

    def heal_internal(self, amount: int) -> None:
        self.current_hp = min(self.current_hp + amount, self.max_hp)


def create_monster_creature(monster: "MonsterModel", rng: Optional[random.Random] = None) -> Creature:
    """Mirrors CombatState.CreateCreature + Creature.SetUniqueMonsterHpValue,
    minus the multi-enemy uniqueness rule (there's only ever one enemy)."""
    rng = rng or random.Random()
    hp = rng.randint(monster.min_initial_hp, monster.max_initial_hp)
    return Creature(side=CombatSide.ENEMY, current_hp=hp, max_hp=hp, monster=monster)
