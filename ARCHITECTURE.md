# Architecture

A transformer network that plays *Slay the Spire 2*, trained against a Python
reimplementation of a subset of the game's mechanics.

## Overview

The system has three parts:

1. **Python simulator** — a reimplementation of a subset of STS2 mechanics.
   This is the ground-truth environment: it generates training data, executes
   actions during RL, and serves as the reference the model's predictions are
   checked against.
2. **Entity encoders** — one or a few small networks that convert each game
   entity (card, relic, player, monster) into a single token. Encoders are
   built from entity *attributes* (cost, type, effect parameters, upgrade
   state, HP, buffs/debuffs, ...) rather than only per-ID embeddings, so they
   generalize to modified/upgraded entities and to a card pool that grows over
   time.
3. **Main transformer** — consumes the set of entity tokens and produces:
   - **Action outputs** (the policy). Actions in STS are pointer-shaped —
     "play card X targeting monster Y", "pick 1 of 3 rewards" — so action
     heads are attention/pointer selections over the entity tokens rather
     than a fixed-size action head. This handles variable hand sizes and
     monster counts for free.
   - **Event predictions** (a diagnostic head, see below).

## Event-prediction head

Given a state and an action, the model predicts the sequence of events that
results (damage dealt, statuses applied, cards drawn, and so on).

This head is **diagnostic, not load-bearing**: the policy never plans with it,
since the real simulator is always available. Its purposes are:

- **Representation learning** — the pretraining objective forces the encoder
  tokens to contain the information that actually determines outcomes.
- **Debugging** — the event vocabulary is human-readable so a predicted
  rollout can be printed next to the simulator's actual rollout and diffed.
  A wrong prediction is informative ("the model doesn't know Vulnerable
  multiplies damage") before any RL compute is spent.

Because it is diagnostic, its accuracy bar is modest, and it is a detachable
head on the shared encoder: at RL time it can be frozen or dropped without
touching the policy path, or kept running in eval mode to watch whether world
understanding degrades as the policy shifts distribution.

Prediction is autoregressive over events, which naturally handles the
stochasticity of card plays (draws, enemy AI rolls, random targeting): the
model conditions on RNG outcomes as they are revealed rather than trying to
predict a deterministic outcome.

## Training plan

**Phase 1 — supervised pretraining.** Train the encoders + event head to
predict event sequences from card plays. Initial data comes from a
random-play agent in the simulator.

Data is effectively free: the simulator generates unlimited labeled
(state, action → events) samples on demand, so every batch can be fresh and
overfitting the event head is not a concern. The constraint is *coverage*,
not quantity — random play almost never reaches strong-synergy states (high
strength, stacked powers, big decks). Two mitigations:

- **Synthetic state construction** — combat states are constructed directly
  (randomized HP, buffs/debuffs, hand contents, energy) rather than only
  reached by playing from turn 1, giving dense coverage of the mechanics
  space independent of any policy.
- **Iteration** — once RL produces better trajectories, the event head is
  periodically retrained/fine-tuned on the agent's own data.

**Phase 2 — reinforcement learning.** Train the policy heads against the
simulator, starting from the pretrained encoder. This is the riskiest link in
the chain, so it should be exercised early rather than after over-polishing
the event head.

## Simulator design constraints

- **State is plain, constructible data.** Any combat state can be built
  directly and set, not only reached through play. This enables synthetic
  data generation and doubles as the basis for unit-testing the simulator.
- **Fast enough for in-process, on-the-fly data generation** during training,
  avoiding a dataset pipeline entirely if possible.

## Scope

Full runs (pathing, shops, events, rest sites, potions) are out of scope
initially. The first milestone is **combat only** with a fixed small
card/relic/enemy pool, working end-to-end: sim → pretraining → RL → an agent
that learns combat. Everything else layers on after that.
