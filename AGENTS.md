# sts2-transformer

Tooling built against *Slay the Spire 2* (Early Access). The game is built with
Godot 4 + C#/.NET (CoreCLR, not Mono/IL2CPP) and its main assembly is
unobfuscated.

## `decomp/`

Decompiled C# source of the game's main assembly (`sts2.dll`), generated with
`ilspycmd`. This is a **read-only reference artifact**, not hand-written
project code — do not edit files under `decomp/`. Use it to understand game
internals (data structures, combat/entity logic, save format, etc.) before
implementing anything in this project.

- Source version: `v0.108.0`, commit `58694f64` — see `decomp/SOURCE_VERSION.json`.
- Original DLL location: `C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64\sts2.dll`
- XML doc comments (from the original source) are copied alongside at `decomp/sts2.xml`.
- Namespace root: `MegaCrit.Sts2.*`. Notable areas: `Core.Combat`,
  `Core.Entities.Actions`, `Core.CardSelection`, `Core.AutoSlay` (an
  existing bot/automation harness), `Core.DevConsole`.

### Regenerating after a game update

The game updates in place, so `decomp/` will drift from the installed build
over time. To refresh:

```bash
dotnet tool install -g ilspycmd --version 9.1.0.7988   # pin this version — 10.1.0 fails to install (broken NuGet package metadata)
ilspycmd -p -o decomp "C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64\sts2.dll"
cp "C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64\sts2.xml" decomp\sts2.xml
```

Update `decomp/SOURCE_VERSION.json` with the new version/commit from the
game's `release_info.json` after regenerating.
