# Tokenizer

Word-level tokenizer for game description text (cards, relics, powers, ...),
feeding the entity encoders in [ARCHITECTURE.md](ARCHITECTURE.md).
Implemented under `model/tokenizer/`.

## Stability contract

The tokenizer must **not** change when the sim gains cards or when the game
patches in new content. Two rules make that hold:

1. **Vocabulary comes from the game's text, not the sim's.** It is built once
   from the full English localization tables in `decomp/pck/localization/eng/`
   (every card/relic/power/potion in the game, not just what the sim
   implements), then checked in as a frozen artifact stamped with the game
   version from `decomp/SOURCE_VERSION.json`. Sim growth can never produce an
   out-of-vocab word because the sim must use the game's description strings
   verbatim (sim entities carry their loc-table entry ID; hand-written
   description text is forbidden).
2. **Entity titles never enter the vocabulary.** Every titled entity's name
   (cards, relics, powers, potions, monsters, orbs, enchantments, afflictions,
   events, encounters) is an open class — every patch adds more — so a title
   occurring inside a description is substituted with a *reference ID block*
   (`<REF_START> cards <ID_0> <ID_F> <ID_2>`, ...) at tokenize time. Only the closed
   class of mechanics words in description templates ("deal", "damage",
   "draw", "exhaust", pile names, card types, ...) becomes vocabulary.

A game update therefore only ever *adds* mechanics words (new keyword text),
which is a reviewed, versioned vocab regeneration — never a per-sim-change
one. Reference capacity is not a vocab constant either (see "The scheme"
below), so no future scope growth can shift token IDs.

## Token classes

| Class | Examples | Notes |
|---|---|---|
| Mechanics words | `deal`, `damage`, `block`, `exhaust`, `hand` | From description templates, lowercased. One word = one token, split on whitespace; spaces are implicit and not part of any token. Doubles as the namespace tag inside a reference ID block (see `<REF_START>` below) — most referenceable tables' own names (`cards`, `relics`, `powers`, `potions`, `monsters`, `orbs`, `afflictions`) are ordinary words in this set, since each occurs literally in the game's text on its own (e.g. "draw a card", "ALL Claw cards"). The exceptions are `enchantments`, `events`, and `encounters`, whose plural table names never occur literally in the scanned text, so they're force-added as tag-only words (see "The scheme"). |
| `<REF_START>` | `<REF_START>` | A single, generic token that opens every reference ID block, regardless of which table the referenced entity comes from. Followed by a namespace word (from the mechanics-words class above) and then `ID_WIDTH` ID digits: `<REF_START> cards <ID_0> <ID_F> <ID_2>`. Fixed like the specials below, not derived from `decomp/`. |
| ID digits | `<ID_0>`–`<ID_F>` | Base-16 identity digits: exactly `ID_WIDTH = 3` of them follow a reference's namespace word, spelling the entity's per-episode ordinal (4096 IDs per namespace). Disjoint from the text digits below — identity is meaning-free and re-randomized every sample, so sharing rows with magnitude digits would inject identity noise into number semantics. |
| Digits | `0`–`9` | Numbers are emitted digit-by-digit (`18` → `1` `8`), so any magnitude works with a 10-token closed class. The one deliberate exception to one-word-one-token. |
| Symbols | `<ENERGY>`, `<STAR>`, `+`, `%`, `.`, `,`, `:`, `X` | Energy/star icon glyphs render to `<ENERGY>`/`<STAR>` (`starIcons()`/`singleStarIcon` render just as consistently to a single fixed icon regardless of repeat count). `+` marks an upgraded reference (`Minion Strike+` → `<REF_START> cards <ID_x> <ID_y> <ID_z>` `+`, following the block). `.`/`,`/`:` are sentence-structure punctuation, kept as tokens rather than stripped like purely decorative marks (quotes, parens, `?`, `;`) — they mark clause/sentence boundaries the model would otherwise lose (`"Deal 6 damage. Draw 2 cards."` must stay distinguishable from a version with the sentences merged). Semicolons never occur in the game's descriptions, so they aren't a token class. Standalone capital `X` is the game's placeholder for a value determined elsewhere ("Deal X damage", "X times", "cost X cards") — captured before lowercasing so it stays a fixed symbol token distinct from the ordinary lowercase `x` used as a bare multiplier suffix ("2x" the damage). |
| Specials | `<PAD>`, `<UNK>` | `<PAD>` fills variable-length sequences out to rectangular batches and is masked out of attention/loss. `<UNK>` must never occur in practice — it exists so a runtime OOV is loggable instead of a crash, and any occurrence is a bug. |

`<REF_START>`, the namespace word, and the ID-digit embeddings are **learned
but meaning-free with respect to identity**: ordinal assignment is
re-randomized every training sample, so only the namespace word carries real
(fixed) meaning — which table the entity belongs to — while `<REF_START>`
and the digits carry none. The same embedding table entries are used (a) for
the reference block inside description text and (b) as the identity tag on
that entity's encoder output block — sharing them is what lets the main
transformer's attention bind a reference in one description to the entity it
names (see "Binding" below).

## Pipeline (raw template → token IDs)

Raw loc entries look like:

```
"Deal {Damage:diff()} damage.\nAdd a [gold]Dazed[/gold] into your [gold]Discard Pile[/gold]."
```

1. **Render** (sim side, mirroring the game's `GetFormattedText`, simplified):
   fill SmartFormat placeholders with the entity's current concrete values,
   pick plural branches (`{Cards:plural:Shiv|Shivs}`), pick upgrade branches
   (`{IfUpgraded:show:...|...}`), render `energyIcons()`/`starIcons()` to
   `<ENERGY>`/`<STAR>` glyphs.
2. **Strip markup**: `[gold]`, `[blue]`, `[purple]`, `[red]` tags are
   cosmetic — drop them (but see "Reference substitution details" below:
   they are *used* before being dropped).
3. **Substitute references**: match entity titles in the text against a
   reference lexicon and replace each with its reference ID block
   (`<REF_START>` + namespace word + `ID_WIDTH` digits, `+` after for an
   upgraded card) *before* word splitting (titles can be multi-word:
   `Minion Strike`, `Sovereign Blade`). Which ordinal each entity holds comes
   from the per-episode assignment map.
4. **Normalize + split**: lowercase, treat `\n` as whitespace, drop purely
   decorative punctuation (`'"();?`), isolate sentence-structure punctuation
   (`.,:`) as standalone symbol tokens, split hyphenated words on the hyphen
   (`0-cost` → `0`, `cost`), split numbers into digits, split on whitespace.
5. **Map to IDs** against the frozen vocab.

Steps 2–5 are the tokenizer proper; step 1 belongs to the sim's
entity-description rendering, but the vocab build must enumerate *all*
branches of step 1 (both plural forms, both upgrade forms) so every renderable
word is covered.

## Reference substitution details

The hard part. The reference lexicon maps surface forms → entity ID, built
from the loc tables' `.title` entries plus derived forms:

- plural forms as they appear in plural branches (`Shivs` → SHIV),
- upgraded forms (`Minion Strike+` → MINION_STRIKE, upgraded),
- hardcoded literal plurals that never go through a `{X:plural:...}`
  placeholder (e.g. `HANG_POWER`'s "All Hangs deal...", relics hardcoding
  "Strikes"/"Defends" to mean "cards named Strike/Defend") — for a
  single-word title, `title + "s"` is indistinguishable from an ordinary
  plural English word, so a candidate is only added as a surface form if it
  actually occurs as literal (placeholder-stripped) text somewhere in the
  corpus, the same cross-referencing safety property used for
  placeholder-derived plurals,
- possessives if they occur.

Matching is longest-first so `Minion Strike` wins over any single-word title.

Text signals alone are not enough, but the decomp source provides ground
truth: entity models declare **hover tips** for the entities their
description references — e.g. `GraveWarden.cs` has
`ExtraHoverTips => HoverTipFactory.FromCard<Soul>()`. These are typed,
per-entity declarations (`FromCard<T>`, `FromPower<T>`, `FromRelic<T>`,
`FromPotion<T>`, ...) and they can be extracted from
`decomp/src/MegaCrit.Sts2.Core.Models.*` with a simple grep/parse. The
extraction must sweep all model namespaces, not just `Models.Cards` —
relics, powers, potions, afflictions, enchantments, and events declare
hover tips too (e.g. `HoverTipFactory.FromForge()` tips Sovereign Blade
from outside any card model). That
gives each description an expected-reference list to match against, which
resolves the known hazards:

- **Unmarked references.** Most references are `[gold]`-wrapped
  (`[gold]Dazed[/gold]`) — but not all: `CLAW.description` says "ALL Claw
  cards" with no markup. So matching must work on plain text; markup and the
  hover-tip list are confidence signals, not requirements.
- **Self-references.** The one systematic gap in hover tips: a card never
  declares a tip for itself, so Claw's reference to `Claw` has no hover tip.
  "Own title appearing in own description" is accepted as a reference
  alongside the declared list.
- **Title/word collisions.** Titles like `Strike`, `Fuel`, `Debris`, `Souls`
  collide with ordinary description words. The hover-tip list settles most
  cases: a colliding word is only a reference if the entity declares (or is)
  that entity. Secondary signals: match case-sensitively against the
  original (pre-lowercasing) text — titles are capitalized mid-sentence —
  and keep a small reviewed exception list for the residue.

Hover tips are used for cross-checking in both directions: a title match
with no corresponding hover tip, or a declared card/relic/power/potion tip
whose title never matches in the text, is printed by the build step for
manual review. `FromKeyword` tips point at keyword text (vocab words, not
references) and are ignored.

Class words are **not** references: `Attack`/`Skill`/`Power`/`Status`/`Curse`
("a random Attack") are card *types* and stay ordinary vocab words, as do
keyword terms with their own semantics (`Exhaust`, `Ethereal`, pile names).
The rule of thumb: if it has a `.title` entry in a referenceable entity table
(any of cards/relics/powers/potions/monsters/orbs/enchantments/afflictions/
events/encounters), it's a reference; if it lives in `card_keywords.json` or is
un-titled mechanics text, it's vocab.

When two tables claim the same surface form the lexicon resolves it by table
order (later wins — see `REFERENCEABLE_TABLES`). `encounters` is ordered first,
i.e. lowest priority, because its titles are just its constituent monsters'
names ("Axebot", "Queen") or combat-group labels, and some are shared across
several encounter IDs: a bare "Axebot" in prose must resolve to the *monster*,
not the encounter. Encounters still get their own namespace (an encounter is an
entity with a prepend tag, and its link to its monsters is an entity-encoding
concern) and still win the titles that are genuinely encounter-only ("Cultists",
"Group of Slimes", ...).

## The scheme

A reference is a single generic start marker, a namespace word, and a fixed
number of base-16 ID digits:

```
Add a Dazed into your Discard Pile.
→  add a <REF_START> cards <ID_0> <ID_F> <ID_2> into your discard pile .
```

Compared to giving each namespace a fixed slot pool (`CARD_0..N`, one row per
possible identity), this compositional scheme buys three things: it removes
capacity from the vocab entirely (there's no per-namespace pool to
outgrow), it trains `<REF_START>` and the 16 ID-digit rows extremely densely
(every reference of any kind fires `<REF_START>`, versus spreading usage
across hundreds of near-never-seen slot rows), and widening capacity later
touches no vocab token. Its price: identity becomes a digit sequence the
model must compose, and entities sharing a digit get spuriously similar
surface forms (pure noise under random assignment, which the model must
learn to see past) — accepted as the cost of scalability.

The namespace word is not a dedicated marker token (`<CARD_REF>`, ...) but
the referenceable table's own name (`cards`, `orbs`, ...), reused as-is: it's
usually already an ordinary, densely-trained mechanics word, and its meaning
as "this reference names a card" isn't in tension with its meaning as an
ordinary noun, unlike the ID digits, so sharing the row costs nothing. This
also means a genuinely new referenceable table usually costs zero *dedicated*
vocab tokens, as long as its name already occurs in game text (the common
case); table additions are rare regardless, since they're a different, much
smaller class of change than the per-entity growth (new cards, new relics,
...) this scheme was built to absorb for free.

A few table names don't occur in the scanned text: `enchantments` (prose only
ever says the singular "enchantment"), and `events`/`encounters` (titles-only
tables whose plural names never appear in a scanned description). Rather than
special-case their namespace tags, `build_vocab.py` force-adds every
referenceable table's name to the vocab (see "Vocab build"), so these become
*tag-only* words — carrying no free-text occurrences, but trained just as
densely as any namespace tag, since each fires on every reference block of its
type and every such entity's prepend tag. This also makes the scheme robust to
a future patch dropping some other table's name from prose: that name simply
becomes tag-only too, never an `<UNK>`.

Details:

- **Per-episode random assignment.** Each episode assigns every entity a
  distinct ordinal, sampled uniformly *without replacement from the full
  `[0, 4096)` range* of its namespace — not densely from 0, so every digit
  token gets trained in every position and low digits carry no
  "assigned-first" signal. Ordinals are meaning-free identity, re-randomized
  every training sample: the model can never memorize "0F2 means Dazed" and
  must read the referenced entity's attributes and description instead,
  which is what generalizes to modified entities and patched-in content.
- **Fixed width, no terminator.** Exactly `ID_WIDTH = 3` digits after the
  namespace word, always. Parsing is deterministic without an end token, and
  4096 IDs per namespace comfortably exceeds any one episode's entity count,
  including cards — the largest referenceable table at 593 concrete models
  (see `count_entities.py`, the sizing reference for this constant). Widening
  further adds **zero** vocab tokens and shifts no token IDs — it changes
  sequence shape only, a reviewed constant change like any other (it still
  invalidates trained checkpoints, as any input-format change does).
- **ID digits are not text digits.** `<ID_0>..<ID_F>` are disjoint from
  `0`–`9`. Text digits carry magnitude ("deal 12 damage"); ID digits are
  identity atoms whose binding is re-randomized every sample. Sharing rows
  would inject identity noise into number semantics.
- **The upgrade marker follows the block**: `Minion Strike+` →
  `<REF_START> cards <ID_x> <ID_y> <ID_z>` `+`.

## Binding

The `<REF_START>`, namespace-word, and ID-digit embeddings are shared between
description text (inside the entity encoders' inputs) and the main
transformer's sequence, where each entity enters as a *prepended ID block*:

```
<REF_START> cards <ID_0> <ID_F> <ID_2> [entity encoder output]
<REF_START> monsters <ID_0> <ID_3> <ID_1> [entity encoder output]
```

An entity whose description references `0F2` pools that fact into its
encoder output; the main transformer binds it to the entity tagged `0F2` by
ordinary attention over ordinary tokens — the same shared-embedding glue a
single-token identity scheme would rely on, spread over five rows instead
of one. This costs positions per entity (a combat state's ~60–100
entities become a few hundred extra positions: negligible), buys zero
bespoke architecture, and keeps identity human-visible in the sequence for
debugging, in line with the diagnostic philosophy of the event head in
[ARCHITECTURE.md](ARCHITECTURE.md).

If sequence length ever bites (full-run scope), the known compression is a
*composed tag vector* — a learned linear over the same digit embeddings,
added to the encoder output, one position per entity — which is a
model-side change that touches no tokenizer artifact.

## Vocab build

Everything tokenizer-related lives in `model/tokenizer/` — the runtime module,
the build script, and the frozen artifacts.

`model/tokenizer/build_vocab.py` is the single build entry point: one run
produces every artifact (vocab, reference lexicon, expected-reference list).
It takes **no parameters** — the output must be a pure function of `decomp/`
plus the script itself, so any rebuild is bit-identical and CI can rebuild
and compare. `ID_WIDTH` and the `<REF_START>`/ID-digit token lists are named
constants at the top of the script, not CLI arguments; changing `ID_WIDTH`
is a reviewed diff like any other vocab change (and, since it's an
input-format change, invalidates trained checkpoints even though it adds no
tokens).

Steps:

1. Read the gameplay tables from `decomp/pck/localization/eng/`: `cards`,
   `card_keywords`, `powers`, `relics`, `potions`, `orbs`, `afflictions`,
   `enchantments`, `modifiers`, `intents`, and — titles only, for the
   reference lexicon — `monsters`, `events`, and `encounters`. Include all of
   them from day one even though the first milestone is combat-only — scope
   growth must not change the vocab.
2. Take description-like fields (`.description`, `.smartDescription`,
   `.selectionScreenPrompt`, ...); skip flavor text.
3. Expand every SmartFormat branch, apply the normalization pipeline with
   titles substituted out, collect the word set. Force-add every referenceable
   table's own name (`cards`, `orbs`, ...) to that word set — each doubles as a
   namespace tag, so the runtime would otherwise emit `<UNK>` for it. Most are
   already present from ordinary text; the rest (currently `enchantments`,
   `events`, `encounters`) become tag-only words (see "The scheme").
4. Emit `model/tokenizer/vocab.json`: sorted word list + `<REF_START>`/
   ID-digit/digit/symbol/special tokens, plus `ID_WIDTH`, the game version,
   and a content hash. Checked into git; regeneration after a game update is
   a reviewed diff (expect additions to the word list only).

The reference lexicon (title surface form → entity ID) is emitted alongside,
since both the tokenizer and the sim's episode-assignment code need it — as
is the per-entity expected-reference list extracted from the hover-tip
declarations in `decomp/src` (the build's only input besides the loc
tables).

## Runtime API

```python
class Tokenizer:
    def __init__(self, vocab_path: Path): ...
    # assignment: entity ID -> per-namespace ordinal in [0, 16**ID_WIDTH),
    # chosen per episode by the trainer; the namespace word is derived from
    # the entity ID's table prefix ("cards.DAZED" -> "cards", reused as-is)
    def tokenize(self, rendered_text: str, assignment: Mapping[str, int]) -> list[int]: ...
    def decode(self, ids: Sequence[int]) -> str: ...   # for debugging/goldens
```

Stateless apart from the loaded vocab; the per-episode randomness lives in
whoever constructs `assignment`. `decode` reassembles a `<REF_START>` +
namespace + digit run into something readable (`<REF:cards:0F2>`-style) so
goldens stay legible. Assignment ordinals that don't fit `ID_WIDTH`
(`>= 16**ID_WIDTH`) are rejected (see "Testing" below).

## Layout

| File | Role |
|---|---|
| `loc_tables.py` | Loads `decomp/pck/localization/eng/*.json` into `{entry_id: {field: text}}` per table; knows which fields are description-like vs. flavor text. |
| `text_template.py` | SmartFormat branch expansion (vocab build only) and the shared `normalize_and_split` / `strip_tags` normalization used by both the build and the runtime tokenizer. |
| `reference_lexicon.py` | Builds the surface-form → entity lexicon (titles, plurals, upgraded forms) and `ReferenceMatcher`, the longest-first matcher used to substitute titles with reference ID blocks. |
| `hover_tips.py` | Scrapes `ExtraHoverTips` declarations out of `decomp/src` to get each entity's expected-reference list, used to cross-check the lexicon's matches. |
| `build_vocab.py` | The single build entry point (no parameters — pure function of `decomp/`). Produces `vocab.json`, `reference_lexicon.json`, `expected_references.json`. |
| `tokenizer.py` | Runtime `Tokenizer` class: `tokenize(rendered_text, assignment) -> list[int]`, `decode(ids) -> str`. |
| `vocab.json`, `reference_lexicon.json`, `expected_references.json` | Frozen, checked-in build artifacts. |
| `tests/test_build_vocab.py` | OOV sweep + "checked-in artifacts match a fresh rebuild" (the CI gate). |
| `tests/test_tokenizer.py` | Substitution goldens and the permutation-invariance test. |

## Running it

```bash
# Rebuild vocab.json / reference_lexicon.json / expected_references.json
# from decomp/ (only needed after decomp/ is regenerated, i.e. a game update)
uv run python -m model.tokenizer.build_vocab

# Run the tokenizer test suite
uv run pytest model/tokenizer/tests
```

`build_vocab` prints `WARNING:` lines for hover-tip cross-check mismatches
(a text reference with no declared hover tip, or vice versa) — these are for
manual review, not build failures; the current run prints 100 of them (mostly
`monsters.OSTY` combat-log references and `cards.SOVEREIGN_BLADE` hover tips
declared on cards whose rendered text picks a branch that doesn't literally
say "Sovereign Blade"). A separate class of warning, "N unrecognized
placeholder pattern(s)", *is* asserted on in `test_no_unrecognized_placeholder_patterns`
and must stay empty.

## Current vocab (v0.108.0, commit 58694f64)

556 tokens total:

- 2 specials (`<PAD>`, `<UNK>`)
- 10 digits (`0`–`9`)
- 8 symbols (`<ENERGY>`, `<STAR>`, `+`, `%`, `.`, `,`, `:`, `X`)
- 1 reference start marker (`<REF_START>`)
- 16 ID digits (`<ID_0>`–`<ID_F>`)
- 519 mechanics words (includes `cards`, `relics`, `powers`, `potions`,
  `monsters`, `orbs`, `afflictions`, and the tag-only `enchantments`,
  `events`, `encounters` — reused as reference namespace tags — and `x`, the
  ordinary lowercase multiplier suffix, distinct from the symbol `X`)

`ID_WIDTH = 3`, so each reference spells 3 of the 16 ID-digit rows, not
2 — a pure sequence-shape change that, as "The scheme" describes, left this
token count untouched. Regenerating after a game update only ever *adds* to
the mechanics-words group; a diff touching any other count is a red flag
worth double-checking against the stability contract above.

## Testing

- **OOV sweep**: every description in every table, all branches expanded,
  tokenizes with zero `<UNK>`. Enforced as "a fresh rebuild from `decomp/`
  exactly matches the checked-in `vocab.json`" — if `decomp/` has been
  regenerated (new mechanics words) without rebuilding the vocab, this
  fails, and CI must catch it.
- **Substitution goldens**: hand-checked token streams for the tricky cases —
  plural references (Blade Dance), nested plural+upgrade branches (Charge),
  unmarked references (Claw), multi-word titles (Sovereign Blade/Minion
  Strike), sentence-structure punctuation kept as symbol tokens
  (Afterimage's comma, periods throughout), the `X` keyword staying distinct
  from the lowercase `x` multiplier suffix (Skewer vs. Reflective Fortress).
- **Permutation test**: tokenizing the same text under two different
  assignments yields identical streams up to remapping the ID digit blocks
  (a block is remapped as a unit, not digit-by-digit) — and later, at the
  model level, permuting the assignment must not change policy/event
  predictions.
- **Range check**: assignment ordinals must fit `ID_WIDTH` (reject
  `>= 16**ID_WIDTH`).

## Open decisions

- Whether the event-prediction head, if its event stream needs to *name*
  entities, reuses the marker + ID-digit tokens as its naming currency
  (natural fit) or stays a fully separate vocabulary.
