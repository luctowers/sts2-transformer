"""Mirrors MegaCrit.Sts2.Core.Combat.History.CombatHistory.

An append-only log of every Event dispatched during a combat - the
ground-truth trajectory the event-prediction head is trained against.
"""

from __future__ import annotations

from typing import List, Type, TypeVar

from engine.combat.events import Event

E = TypeVar("E", bound=Event)


class CombatHistory:
    def __init__(self):
        self.entries: List[Event] = []

    def add(self, event: Event) -> None:
        self.entries.append(event)

    def of_type(self, event_type: Type[E]) -> List[E]:
        return [entry for entry in self.entries if isinstance(entry, event_type)]

    def clear(self) -> None:
        self.entries.clear()
