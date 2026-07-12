"""A single, minimal training enemy: attacks on odd turns, does nothing on
even turns. Stand-in for a real ported monster (e.g. Cultist, Jaw Worm)."""

from __future__ import annotations

from engine.entities.intents.intent import Intent, IntentType
from engine.models.monster_model import MonsterModel


class Dummy(MonsterModel):
    title = "Dummy"
    min_initial_hp = 40
    max_initial_hp = 44

    attack_damage = 6

    def get_intent(self, turn_number: int) -> Intent:
        if turn_number % 2 == 1:
            return Intent(IntentType.ATTACK, damage=self.attack_damage)
        return Intent(IntentType.NONE)
