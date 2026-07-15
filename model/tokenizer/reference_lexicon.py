"""Builds the reference lexicon: entity title (and derived surface forms)
-> (table, entry_id). See docs/TOKENIZER.md "Reference substitution details".

Entity titles are an open class (every patch adds more) so they must never
become vocab words - a title occurring in description text is substituted
with a reference ID block instead. This module finds every surface form a
title can take (base, plural, upgraded) so that substitution step can run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from model.tokenizer import loc_tables
from model.tokenizer.text_template import split_top_level, strip_tags

_NESTED_BRANCH_RE = re.compile(r"\{[^{}:]+:(?:show|plural):([^{}]*)\}")


@dataclass(frozen=True)
class ReferenceEntry:
    table: str
    entry_id: str
    upgraded: bool = False


def _all_raw_texts() -> list[str]:
    texts = []
    for table, fields in loc_tables.DESCRIPTION_FIELDS.items():
        entries = loc_tables.entries_for_table(table)
        for entry_fields in entries.values():
            for field in fields:
                if field in entry_fields and entry_fields[field]:
                    texts.append(entry_fields[field])
    return texts


def _iter_plural_rests(text: str):
    """Yield the `rest` text of every `{Name:plural:rest}` placeholder in
    `text`, at any nesting depth (see CHARGE.description for a plural
    placeholder whose own branches each contain a further nested
    IfUpgraded:show placeholder)."""
    i, n = 0, len(text)
    while i < n:
        if text[i] == "{":
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                j += 1
            body = text[i + 1 : j - 1]
            if ":" in body:
                _name, rest = body.split(":", 1)
                if rest.startswith("plural:"):
                    yield rest[len("plural:"):]
            yield from _iter_plural_rests(body)
            i = j
        else:
            i += 1


def _resolve_leaf_variants(text: str) -> list[str]:
    """Resolve at most one nested show:/plural: placeholder within a plural
    branch's own text into its ordered list of concrete leaf strings (tags
    stripped). Plain text with no nested placeholder resolves to itself."""
    m = _NESTED_BRANCH_RE.search(text)
    if not m:
        return [strip_tags(text).strip()]
    variants = []
    for branch in split_top_level(m.group(1), "|"):
        candidate = text[: m.start()] + branch + text[m.end():]
        variants.append(strip_tags(candidate).strip())
    return variants


def _strip_placeholders(text: str) -> str:
    """Remove every (possibly nested) `{...}` placeholder span, leaving only
    literal template text. Used to find hardcoded literal plurals that never
    go through a `{X:plural:...}` placeholder (e.g. relic text hardcoding
    "Strikes"/"Defends" to mean "cards named Strike/Defend") without
    mistaking a DynamicVar's own name (e.g. the `Sacrifices` in
    `{Sacrifices:plural:sacrifice|...}`) for literal text."""
    out = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == "{":
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                j += 1
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def build_reference_lexicon() -> dict[str, ReferenceEntry]:
    lexicon: dict[str, ReferenceEntry] = {}
    raw_texts = _all_raw_texts()

    for table in loc_tables.REFERENCEABLE_TABLES:
        for entry_id, title in loc_tables.titles_for_table(table).items():
            if not title:
                continue
            lexicon[title] = ReferenceEntry(table, entry_id)
            # Cards are the only entity with an upgraded rendering ("+").
            if table == "cards":
                lexicon[title + "+"] = ReferenceEntry(table, entry_id, upgraded=True)

    # Plural forms: {X:plural:singular_branch|plural_branch}, where each
    # branch may itself be a plain title or a nested IfUpgraded:show
    # placeholder (Charge's "Minion Dive Bomb(s)(+)"). A branch's variants
    # are registered as new surface forms wherever its positional
    # counterpart in the other branch is already a known surface form.
    for raw in raw_texts:
        for rest in _iter_plural_rests(raw):
            branches = split_top_level(rest, "|")
            if len(branches) != 2:
                continue
            variants = [_resolve_leaf_variants(b) for b in branches]
            if len(variants[0]) != len(variants[1]):
                continue
            for a, b in (variants, variants[::-1]):
                for known, derived in zip(a, b):
                    if known in lexicon and derived:
                        lexicon.setdefault(derived, lexicon[known])

    # Hardcoded literal plurals: a few descriptions pluralize a single-word
    # title directly in template text instead of through a
    # `{X:plural:...}` placeholder (HANG_POWER's "All Hangs deal...",
    # relics hardcoding "Strikes"/"Defends"). Only add a regular "+s" form
    # when it actually occurs as literal (placeholder-stripped) text
    # somewhere in the corpus, the same cross-referencing safety property
    # as the placeholder-derived pass above.
    literal_texts = [_strip_placeholders(raw) for raw in raw_texts]
    for title, entry in list(lexicon.items()):
        if entry.upgraded or " " in title:
            continue
        plural = title + "s"
        if plural in lexicon:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(plural)}(?!\w)")
        if any(pattern.search(t) for t in literal_texts):
            lexicon[plural] = entry

    return lexicon


class ReferenceMatcher:
    """Matches lexicon surface forms against text, longest-first.

    Matching is case-sensitive against the original (pre-lowercasing) text,
    since titles are always capitalized where they occur mid-sentence.
    """

    def __init__(self, lexicon: dict[str, ReferenceEntry]):
        self.lexicon = lexicon
        forms = sorted(lexicon.keys(), key=len, reverse=True)
        if forms:
            alternation = "|".join(re.escape(f) for f in forms)
            # Custom word-boundary lookarounds (rather than \b) so a
            # trailing "+" (non-word char) on an upgraded form still counts
            # as bounded.
            self.pattern = re.compile(rf"(?<!\w)(?:{alternation})(?!\w)")
        else:
            self.pattern = None

    def substitute(self, text: str) -> str:
        """Replace every matched surface form in `text` with a single space."""
        if self.pattern is None:
            return text
        return self.pattern.sub(" ", text)

    def find_all(self, text: str) -> set[ReferenceEntry]:
        """Return every lexicon entry whose surface form occurs in `text`."""
        if self.pattern is None:
            return set()
        return {self.lexicon[m.group(0)] for m in self.pattern.finditer(text)}
