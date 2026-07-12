"""Mirrors MegaCrit.Sts2.Core.Combat.CombatManager.

Drives the turn flow: player draws and plays cards, ends their turn, the
enemy acts on its intent, sides switch back. Every state change - drawing,
discarding, shuffling, spending energy, turn boundaries, the enemy's move -
is expressed as an Event and applied through CombatState.dispatch (see
engine/combat/events.py). CombatManager itself never mutates a Creature or
CardPile directly; it only decides *which* events happen and in what order.

Simplified from the decomp in every way its async/multiplayer/hooks
machinery doesn't apply here:
- Synchronous, no GameAction queue/PlayerChoiceContext - there's nothing in
  this scope (no targeting choices beyond "the one enemy") that needs to
  pause for player input.
- One CombatManager per combat (constructed with its CombatState), not a
  process-wide singleton, so many combats can run in parallel for training.
"""

from __future__ import annotations

import random
from typing import List, Optional

from engine.combat.combat_side import CombatSide
from engine.combat.combat_state import CombatState
from engine.combat.events import (
    BlockCleared,
    CardMoved,
    CardPlayed,
    CombatEnded,
    DeckShuffled,
    EnergyReset,
    EnergySpent,
    MonsterMovePerformed,
    TurnEnded,
    TurnStarted,
)
from engine.commands import creature_cmd
from engine.entities.cards.card_play import CardPlay
from engine.entities.cards.pile_type import PileType
from engine.entities.creatures.creature import Creature
from engine.entities.intents.intent import Intent, IntentType
from engine.entities.players.player import Player
from engine.entities.players.player_combat_state import MAX_CARDS_IN_HAND
from engine.models.card_model import CardModel

BASE_HAND_DRAW_COUNT = 5


class CombatManager:
    def __init__(self, state: CombatState):
        self.state = state
        self._combat_ended_dispatched = False

    def start_combat(self) -> None:
        player = self.state.player
        player.reset_combat_state()
        player.populate_combat_state()
        player.combat_state.draw_pile.shuffle(self.state.rng)
        self._start_player_turn()

    def enemy_intent(self) -> Intent:
        """The intent of the (sole) enemy for the enemy turn coming up this round."""
        enemy = self.state.enemies[0]
        return enemy.monster.get_intent(self.state.round_number)

    def playable_cards(self) -> List[CardModel]:
        pcs = self.state.player.combat_state
        return [card for card in pcs.hand.cards if card.cost <= pcs.energy]

    def play_card(self, card: CardModel, target: Optional[Creature] = None) -> None:
        if self.state.is_over:
            raise RuntimeError("Combat is over.")
        if self.state.current_side != CombatSide.PLAYER:
            raise RuntimeError("It is not the player's turn.")
        pcs = self.state.player.combat_state
        if card not in pcs.hand.cards:
            raise ValueError("Card is not in hand.")
        if card.cost > pcs.energy:
            raise ValueError("Not enough energy to play this card.")
        if not card.is_valid_target(target):
            raise ValueError("Invalid target for this card.")

        player = self.state.player
        self.state.dispatch(CardPlayed(player=player, card=card, target=target))
        self.state.dispatch(EnergySpent(player=player, amount=card.cost))

        card.on_play(self.state, CardPlay(card, target))

        self.state.dispatch(CardMoved(player=player, card=card, frm=PileType.PLAY, to=PileType.DISCARD))
        self._dispatch_combat_ended_if_over()

    def end_turn(self) -> None:
        if self.state.is_over:
            return
        player = self.state.player
        pcs = player.combat_state
        for card in list(pcs.hand.cards):
            self.state.dispatch(CardMoved(player=player, card=card, frm=PileType.HAND, to=PileType.DISCARD))
        self.state.dispatch(TurnEnded())

        self.state.current_side = CombatSide.ENEMY
        self._run_enemy_turn()
        if self._dispatch_combat_ended_if_over():
            return

        self.state.current_side = CombatSide.PLAYER
        self.state.round_number += 1
        pcs.increment_turn_number()
        self._start_player_turn()

    def _start_player_turn(self) -> None:
        self.state.dispatch(TurnStarted())
        player = self.state.player
        pcs = player.combat_state
        self.state.dispatch(EnergyReset(player=player))
        if pcs.turn_number > 1:
            self.state.dispatch(BlockCleared(creature=player.creature))
        self._draw_cards(BASE_HAND_DRAW_COUNT)

    def _draw_cards(self, count: int) -> None:
        player = self.state.player
        pcs = player.combat_state
        for _ in range(count):
            if len(pcs.hand.cards) >= MAX_CARDS_IN_HAND:
                break
            if pcs.draw_pile.is_empty:
                if pcs.discard_pile.is_empty:
                    break
                self.state.dispatch(DeckShuffled(player=player))
            card = pcs.draw_pile.cards[0]
            self.state.dispatch(CardMoved(player=player, card=card, frm=PileType.DRAW, to=PileType.HAND))

    def _run_enemy_turn(self) -> None:
        self.state.dispatch(TurnStarted())
        enemy = self.state.enemies[0]
        self.state.dispatch(BlockCleared(creature=enemy))
        intent = enemy.monster.get_intent(self.state.round_number)
        self.state.dispatch(MonsterMovePerformed(creature=enemy, intent=intent))
        if intent.type == IntentType.ATTACK:
            creature_cmd.damage(self.state, self.state.player.creature, intent.damage, dealer=enemy)
        self.state.dispatch(TurnEnded())

    def _dispatch_combat_ended_if_over(self) -> bool:
        if self.state.is_over and not self._combat_ended_dispatched:
            self.state.dispatch(CombatEnded(player_won=self.state.player_won))
            self._combat_ended_dispatched = True
        return self.state.is_over


def new_combat(
    player: Player,
    enemy: Creature,
    rng: Optional[random.Random] = None,
) -> CombatManager:
    """Build and start a combat between `player` and the single `enemy`."""
    manager = CombatManager(CombatState(player, enemy, rng))
    manager.start_combat()
    return manager
