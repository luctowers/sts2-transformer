"""Mirrors MegaCrit.Sts2.Core.Models.Monsters.MonsterModel.

Simplified to what a single-enemy, no-powers combat needs: an initial HP
range and a rule for what intent it has on a given turn. In the real game
a monster's next move is rolled with weighted RNG and cached until it acts
(MonsterMoveStateMachine); here get_intent is a pure function of the turn
number, so there's nothing to cache or roll.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from engine.entities.intents.intent import Intent


class MonsterModel(ABC):
    title: str = "Monster"
    min_initial_hp: int
    max_initial_hp: int

    @abstractmethod
    def get_intent(self, turn_number: int) -> Intent:
        ...
