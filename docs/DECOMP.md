# `decomp/`

The game is built with Godot 4 + C#/.NET (CoreCLR, not Mono/IL2CPP) and its
main assembly is unobfuscated.

`decomp/` holds read-only reference artifacts extracted from the installed
game — do not edit anything under it. Layout:

- `decomp/src/` — decompiled C# source of the main assembly (`sts2.dll`),
  generated with `ilspycmd`. Use it to understand game internals (data
  structures, combat/entity logic, save format, etc.).
- `decomp/pck/` — data files extracted from the Godot pack
  (`SlayTheSpire2.pck`), currently just the English localization tables
  (`pck/localization/eng/*.json`) — the source of truth for card/relic/power
  text, used to build the tokenizer vocabulary (see
  [TOKENIZER.md](TOKENIZER.md)).
- `decomp/SOURCE_VERSION.json` — game version both artifacts were extracted
  from.

Facts about `decomp/src`:

- Source version: `v0.108.0`, commit `58694f64` — see `decomp/SOURCE_VERSION.json`.
- Original DLL location: `C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64\sts2.dll`
- XML doc comments (from the original source) are copied alongside at `decomp/src/sts2.xml`.
- Namespace root: `MegaCrit.Sts2.*`. Notable areas: `Core.Combat`,
  `Core.Entities.Actions`, `Core.CardSelection`, `Core.AutoSlay` (an
  existing bot/automation harness), `Core.DevConsole`.

## Regenerating after a game update

The game updates in place, so `decomp/` will drift from the installed build
over time. To refresh:

### `decomp/src` (C# source)

```bash
dotnet tool install -g ilspycmd --version 9.1.0.7988   # pin this version — 10.1.0 fails to install (broken NuGet package metadata)
ilspycmd -p -o decomp/src "C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64\sts2.dll"
cp "C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64\sts2.xml" decomp/src/sts2.xml
```

### `decomp/pck` (localization tables)

Uses [GodotPckTool](https://github.com/hhyyrylainen/GodotPckTool) v2.3
(pinned; v2.2+ is required for Godot 4.5's pck format 3), installed as a
standalone exe:

```bash
curl -sLo ~/.local/bin/godotpcktool.exe "https://github.com/hhyyrylainen/GodotPckTool/releases/download/v2.3/godotpcktool.exe"
godotpcktool.exe -p "C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\SlayTheSpire2.pck" \
  -a e -o decomp/pck -i "^localization/(eng/|completion\.json|README\.md)" -q
```

### Version stamp

Update `decomp/SOURCE_VERSION.json` with the new version/commit from the
game's `release_info.json` after regenerating, and rebuild the tokenizer
vocab (its OOV test will fail until you do).
