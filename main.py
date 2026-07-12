"""Demo: plays one combat between a starting-deck Player and a Dummy enemy
using a simple "play everything, attack the enemy" policy, printing the
event log as it happens."""

from __future__ import annotations

import random

from engine.combat.combat_manager import new_combat
from engine.entities.creatures.creature import create_monster_creature
from engine.entities.players.player import Player
from engine.models.cards.starting_deck import starting_deck
from engine.models.monsters.dummy import Dummy


def main():
    rng = random.Random(0)

    player = Player(max_hp=75, max_energy=3, deck=starting_deck())
    enemy = create_monster_creature(Dummy(), rng)

    manager = new_combat(player, enemy, rng)
    state = manager.state

    while not state.is_over:
        playable = manager.playable_cards()
        while playable and not state.is_over:
            card = playable[0]
            target = enemy if card.is_valid_target(enemy) else None
            manager.play_card(card, target)
            playable = manager.playable_cards()
        manager.end_turn()

    for event in state.history.entries:
        print(event)

    print()
    print("Player wins!" if state.player_won else "Player loses!")


if __name__ == "__main__":
    main()
