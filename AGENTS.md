# sts2-transformer

A transformer network that plays *Slay the Spire 2* (Early Access), trained
against a Python reimplementation of a subset of the game's mechanics. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and training plan.

The Python project is managed with [uv](https://docs.astral.sh/uv/) at the
repo root.

## `decomp/`

Read-only reference artifacts extracted from the installed game: decompiled
C# source of the main assembly (`decomp/src/`) and localization tables from
the Godot pack (`decomp/pck/`). Do not read or search under `decomp/` unless
the user explicitly asks or grants permission. See
[docs/DECOMP.md](docs/DECOMP.md) for details and regeneration instructions.
