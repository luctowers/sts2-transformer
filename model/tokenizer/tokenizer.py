"""Runtime tokenizer: turns already-rendered entity description text into
token IDs. See docs/TOKENIZER.md "The scheme" and "Runtime API".

Rendering (filling SmartFormat placeholders with concrete values, picking
plural/upgrade branches, drawing energy/star icons as literal "<ENERGY>" /
"<STAR>" glyphs) is the sim's job and has already happened by the time text
reaches `tokenize()`. This module only does steps 2-5 of the pipeline: strip
markup, substitute entity-title references for reference ID blocks
(`<REF_START>` + namespace word + `ID_WIDTH` digits), normalize and split,
map to vocab IDs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping, Sequence

from model.tokenizer.reference_lexicon import ReferenceEntry, ReferenceMatcher
from model.tokenizer.text_template import normalize_and_split, strip_tags

_ICON_GLYPHS = ("<ENERGY>", "<STAR>")

# Fixed like PAD/UNK below, not derived from decomp/ - opens every reference
# ID block regardless of namespace. The namespace itself is just the
# referenced entity's table name ("cards", "orbs", ...), reused as-is since
# build_vocab.py guarantees it's already an ordinary mechanics word (see
# docs/TOKENIZER.md "The scheme"), so no per-namespace marker token exists.
REF_START = "<REF_START>"
_ID_DIGIT_RE = re.compile(r"^<ID_([0-9A-F])>$")

PAD = "<PAD>"
UNK = "<UNK>"


def _id_digit_tokens(ordinal: int, width: int) -> list[str]:
    """Spell a per-namespace ordinal as `width` base-16 `<ID_x>` tokens,
    most-significant digit first. Raises if the ordinal doesn't fit -
    docs/TOKENIZER.md's "Range check"."""
    if not 0 <= ordinal < 16**width:
        raise ValueError(f"ordinal {ordinal} does not fit ID_WIDTH={width}")
    return [f"<ID_{c}>" for c in format(ordinal, f"0{width}X")]


class Tokenizer:
    def __init__(self, vocab_path: Path):
        with Path(vocab_path).open(encoding="utf-8") as f:
            vocab = json.load(f)

        self.tokens: list[str] = vocab["tokens"]
        self.token_to_id: dict[str, int] = {t: i for i, t in enumerate(self.tokens)}
        self.pad_id = self.token_to_id[PAD]
        self.unk_id = self.token_to_id[UNK]
        # Stamped into vocab.json so the runtime can't disagree with the
        # build (docs/TOKENIZER.md "Vocab build").
        self.id_width: int = vocab["id_width"]

        lexicon_path = Path(vocab_path).parent / "reference_lexicon.json"
        with lexicon_path.open(encoding="utf-8") as f:
            raw_lexicon = json.load(f)
        lexicon = {
            surface: ReferenceEntry(entry["table"], entry["entry_id"], entry["upgraded"])
            for surface, entry in raw_lexicon.items()
        }
        self._matcher = ReferenceMatcher(lexicon)

        icon_alternation = "|".join(re.escape(g) for g in _ICON_GLYPHS)
        self._icon_re = re.compile(icon_alternation)

    def tokenize(self, rendered_text: str, assignment: Mapping[str, int]) -> list[int]:
        """Tokenize already-rendered description text.

        `assignment` maps "table.entry_id" (e.g. "cards.CLAW") to the
        per-namespace ordinal (in `[0, 16**ID_WIDTH)`) assigned to that
        entity for this episode/sample - the same mapping used to tag that
        entity's own encoder output block, which is what lets the main
        transformer's attention bind a reference here to the entity it names
        (see docs/TOKENIZER.md "Binding").
        """
        text = strip_tags(rendered_text)

        tokens: list[str] = []
        pos = 0
        for match in self._iter_matches(text):
            if pos < match.start:
                tokens.extend(self._normalize_literal(text[pos : match.start]))
            tokens.extend(match.tokens(assignment, self.id_width))
            pos = match.end
        if pos < len(text):
            tokens.extend(self._normalize_literal(text[pos:]))

        ids = []
        for tok in tokens:
            token_id = self.token_to_id.get(tok)
            if token_id is None:
                print(f"WARNING: <UNK> token for {tok!r} in {rendered_text!r}")
                token_id = self.unk_id
            ids.append(token_id)
        return ids

    def _normalize_literal(self, text: str) -> list[str]:
        return normalize_and_split(text, split_digits=True)

    def _iter_matches(self, text: str):
        """Yield _Match objects for every reference/icon span in `text`, in
        left-to-right order, longest-reference-first at each position."""
        ref_pattern = self._matcher.pattern
        candidates = []
        if ref_pattern is not None:
            candidates.extend(
                _Match(m.start(), m.end(), ref=self._matcher.lexicon[m.group(0)])
                for m in ref_pattern.finditer(text)
            )
        candidates.extend(
            _Match(m.start(), m.end(), icon=m.group(0)) for m in self._icon_re.finditer(text)
        )
        candidates.sort(key=lambda m: (m.start, -(m.end - m.start)))
        result = []
        last_end = -1
        for m in candidates:
            if m.start >= last_end:
                result.append(m)
                last_end = m.end
        return result

    def decode(self, ids: Sequence[int]) -> str:
        """Reassemble token IDs into a readable string, collapsing each
        `<REF_START>` + namespace + `id_width`-digit run into a single
        `<REF:cards:F2>`-style span so goldens stay legible
        (docs/TOKENIZER.md "Runtime API")."""
        tokens = [self.tokens[i] if 0 <= i < len(self.tokens) else UNK for i in ids]
        out: list[str] = []
        i = 0
        while i < len(tokens):
            block = tokens[i + 2 : i + 2 + self.id_width]
            digit_matches = [_ID_DIGIT_RE.match(t) for t in block]
            if (
                tokens[i] == REF_START
                and i + 1 < len(tokens)
                and len(block) == self.id_width
                and all(digit_matches)
            ):
                namespace = tokens[i + 1]
                digits = "".join(m.group(1) for m in digit_matches)
                out.append(f"<REF:{namespace}:{digits}>")
                i += 2 + self.id_width
            else:
                out.append(tokens[i])
                i += 1
        return " ".join(out)


class _Match:
    def __init__(self, start: int, end: int, *, ref: ReferenceEntry | None = None, icon: str | None = None):
        self.start = start
        self.end = end
        self.ref = ref
        self.icon = icon

    def tokens(self, assignment: Mapping[str, int], id_width: int) -> list[str]:
        if self.ref is not None:
            key = f"{self.ref.table}.{self.ref.entry_id}"
            digits = _id_digit_tokens(assignment[key], id_width)
            block = [REF_START, self.ref.table, *digits]
            return [*block, "+"] if self.ref.upgraded else block
        return [self.icon]
