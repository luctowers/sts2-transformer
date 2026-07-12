"""Mirrors MegaCrit.Sts2.Core.Combat.History.Entries.

A fixed, human-readable vocabulary of everything that can happen in
combat. This is the event-sourcing spine of the engine: **no code outside
this module is allowed to mutate a Creature, CardPile, or PlayerCombatState
directly.** Every mutation is expressed as an Event and applied through
CombatState.dispatch, which is the only thing that calls Event.apply and is
the only thing that appends to CombatState.history.

This matters beyond bookkeeping: docs/ARCHITECTURE.md's event-prediction
head is trained to predict exactly this stream (state, action -> events),
so the event log produced here *is* the training signal, not an
after-the-fact log of it. Routing all mutation through dispatch guarantees
the log is a complete, replayable account of the combat - nothing can
happen that isn't represented in the vocabulary below.

Each event is a plain (mutable) dataclass: fields present at construction
are its inputs (what the caller is requesting), and `apply` fills in any
outcome fields (e.g. DamageDealt.unblocked) as it mutates state - mirroring
decomp's DamageResult being computed as damage resolves. `round_number` and
`side` are stamped in by CombatState.dispatch, not the event's author,
mirroring how CombatHistoryEntry captures them from ICombatState at log
time rather than from the caller.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from engine.combat.combat_side import CombatSide
from engine.entities.cards.pile_type import PileType
from engine.entities.intents.intent import Intent, IntentType

if TYPE_CHECKING:
    from engine.combat.combat_state import CombatState
    from engine.entities.creatures.creature import Creature
    from engine.entities.players.player import Player
    from engine.models.card_model import CardModel


def _card_name(card: "CardModel") -> str:
    return type(card).__name__


def _creature_name(creature: "Creature") -> str:
    if creature.is_player:
        return "Player"
    return creature.monster.title


class Event(ABC):
    """Not a dataclass itself - subclasses declare their own fields via
    @dataclass and inherit these as plain attributes, set by dispatch()."""

    round_number: int
    side: CombatSide

    @abstractmethod
    def apply(self, state: "CombatState") -> None:
        """Mutate `state` to reflect this event. Called exactly once, by
        CombatState.dispatch - never call this directly."""

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    def __str__(self) -> str:
        return f"Rd {self.round_number} ({self.side.name} turn): {self.description}"


@dataclass
class TurnStarted(Event):
    def apply(self, state: "CombatState") -> None:
        pass

    @property
    def description(self) -> str:
        return "Turn started"


@dataclass
class TurnEnded(Event):
    def apply(self, state: "CombatState") -> None:
        pass

    @property
    def description(self) -> str:
        return "Turn ended"


@dataclass
class EnergyReset(Event):
    player: "Player"
    amount: int = field(init=False, default=0)

    def apply(self, state: "CombatState") -> None:
        pcs = self.player.combat_state
        pcs.energy = self.player.max_energy
        self.amount = pcs.energy

    @property
    def description(self) -> str:
        return f"Energy reset to {self.amount}"


@dataclass
class EnergySpent(Event):
    player: "Player"
    amount: int

    def apply(self, state: "CombatState") -> None:
        self.player.combat_state.energy -= self.amount

    @property
    def description(self) -> str:
        return f"Spent {self.amount} energy"


@dataclass
class CardMoved(Event):
    """A single card moving between two of a player's combat piles - draws
    (Draw -> Hand) and discards (Hand/Play -> Discard) are both this."""

    player: "Player"
    card: "CardModel"
    frm: PileType
    to: PileType

    def apply(self, state: "CombatState") -> None:
        pcs = self.player.combat_state
        pcs.get_pile(self.frm).remove(self.card)
        pcs.get_pile(self.to).add(self.card)

    @property
    def description(self) -> str:
        return f"{_card_name(self.card)} moved from {self.frm.name} to {self.to.name}"


@dataclass
class DeckShuffled(Event):
    """The discard pile is shuffled into the draw pile (draw pile was empty)."""

    player: "Player"

    def apply(self, state: "CombatState") -> None:
        pcs = self.player.combat_state
        for card in pcs.discard_pile.clear():
            pcs.draw_pile.add(card)
        pcs.draw_pile.shuffle(state.rng)

    @property
    def description(self) -> str:
        return "Discard pile shuffled into draw pile"


@dataclass
class CardPlayed(Event):
    player: "Player"
    card: "CardModel"
    target: Optional["Creature"]

    def apply(self, state: "CombatState") -> None:
        pcs = self.player.combat_state
        pcs.hand.remove(self.card)
        pcs.play_pile.add(self.card)

    @property
    def description(self) -> str:
        targeting = f" targeting {_creature_name(self.target)}" if self.target else ""
        return f"{_card_name(self.card)} played{targeting}"


@dataclass
class BlockGained(Event):
    creature: "Creature"
    amount: int

    def apply(self, state: "CombatState") -> None:
        self.creature.gain_block_internal(self.amount)

    @property
    def description(self) -> str:
        return f"{_creature_name(self.creature)} gained {self.amount} block"


@dataclass
class BlockCleared(Event):
    creature: "Creature"
    amount: int = field(init=False, default=0)

    def apply(self, state: "CombatState") -> None:
        self.amount = self.creature.block
        self.creature.lose_block_internal(self.amount)

    @property
    def description(self) -> str:
        return f"{_creature_name(self.creature)} lost {self.amount} block"


@dataclass
class DamageDealt(Event):
    target: "Creature"
    amount: int
    dealer: Optional["Creature"] = None
    unblocked: int = field(init=False, default=0)
    blocked: int = field(init=False, default=0)
    was_target_killed: bool = field(init=False, default=False)

    def apply(self, state: "CombatState") -> None:
        if self.target.is_dead or self.amount <= 0:
            return
        self.blocked = self.target.damage_block_internal(self.amount)
        self.unblocked = self.amount - self.blocked
        result = self.target.lose_hp_internal(self.unblocked)
        self.was_target_killed = result.was_target_killed

    @property
    def description(self) -> str:
        target = _creature_name(self.target)
        source = f"{_creature_name(self.dealer)} dealt" if self.dealer else f"{target} took"
        killed = " (killed)" if self.was_target_killed else ""
        return f"{source} {self.unblocked} damage to {target}{killed}"


@dataclass
class MonsterMovePerformed(Event):
    creature: "Creature"
    intent: Intent

    def apply(self, state: "CombatState") -> None:
        pass

    @property
    def description(self) -> str:
        if self.intent.type == IntentType.ATTACK:
            return f"{_creature_name(self.creature)} attacks for {self.intent.damage}"
        return f"{_creature_name(self.creature)} does nothing"


@dataclass
class CombatEnded(Event):
    player_won: bool

    def apply(self, state: "CombatState") -> None:
        pass

    @property
    def description(self) -> str:
        return "Combat won" if self.player_won else "Combat lost"
