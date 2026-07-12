# sts2-transformer

A transformer network that plays *Slay the Spire 2* (Early Access), trained
against a Python reimplementation of a subset of the game's mechanics. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and training plan.

The Python project is managed with [uv](https://docs.astral.sh/uv/) at the
repo root.

## `decomp/`

Decompiled C# source of the game's main assembly — a read-only reference
artifact for understanding game internals. Do not read or search under
`decomp/` unless the user explicitly asks or grants permission. See
[docs/DECOMP.md](docs/DECOMP.md) for details and regeneration instructions.
