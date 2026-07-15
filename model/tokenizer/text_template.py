"""SmartFormat-template branch expansion, for vocab building only.

This is deliberately *not* a full SmartFormat renderer. Rendering concrete
descriptions (filling placeholders with an entity's actual values) is the
sim's job (see docs/TOKENIZER.md pipeline step 1) and happens elsewhere, later.
This module's only purpose is to answer "what literal words could ever
appear here, across every plural/upgrade/conditional branch" so
build_vocab.py can enumerate the closed set of mechanics words - it never
needs to know which branch a real playthrough would pick.

Grammar handled (reverse-engineered from decomp/src's Localization
formatters/DynamicVars and cross-checked against every description in
decomp/pck/localization/eng/*.json - see docs/TOKENIZER.md):

    {Name}                          bare var: numeric or icon value, no text
    {Name:diff()}                   numeric formatters, no text
        (also inverseDiff, percentMore, percentLess, abs, n)
    {Name:energyIcons()}            icon glyph, no vocab text (fixed symbol)
    {Name:starIcons()}              icon glyph, no vocab text (fixed symbol)
    {Name:plural:sing|plur}         2+ branches, all contribute words
    {Name:show:a|b}                 2 branches (IfUpgraded), both contribute
    {Name:choose(A|B|C):x|y|z|def}  N+1 branches (one per enum value + default)
    {Name:cond:<expr>?a|<expr>?b|c} chained ternary; each '|'-segment's text
                                     after its (optional) leading 'expr?' is
                                     a branch
    {Name:a|b}                      generic 2-branch conditional (e.g.
                                     InCombat, IsOstyAlive, OnPlayer), no
                                     formatter keyword
    {}                               nested "current value" inside a branch
"""

from __future__ import annotations

import re

_TAG_RE = re.compile(r"\[/?[a-zA-Z_]+\]")
# Purely decorative punctuation, dropped outright. Includes the curly quotes
# used in a couple of descriptions (e.g. HELLRAISER's "containing
# “Strike”") and "?", the leftover marker in a couple of unused debug
# branches (MAD_SCIENCE's "???"). Sentence-structure punctuation (. , :) is
# NOT here - it's a symbol token instead (see _SYMBOL_CHAR_RE), since it
# carries real clause-boundary information (TOKENIZER.md "Symbols").
_PUNCT_RE = re.compile(r"""['"“”?();]""")
_DIGIT_RUN_RE = re.compile(r"[0-9]+")
_SYMBOL_CHAR_RE = re.compile(r"[%+.,:]")
# Standalone capital "X" - the game's placeholder for a value determined
# elsewhere ("Deal X damage", "X times", "cost X cards") - is a fixed symbol
# token (TOKENIZER.md "Symbols"), not an ordinary word. It must be captured
# before lowercasing, or it collapses into the unrelated lowercase "x" used
# as a bare multiplier suffix ("{Amount}x" -> "2x" the damage).
_X_VAR_RE = re.compile(r"(?<!\w)X(?!\w)")
_X_SENTINEL = "\x00"

_VALUE_ONLY_FORMATTERS = re.compile(
    r"^(diff|inverseDiff|percentMore|percentLess|abs|n)\([^()]*\)$"
)
_ICON_FORMATTERS = re.compile(r"^(energyIcons|starIcons)\([^()]*\)$")
_CHOOSE_RE = re.compile(r"^choose\(([^()]*)\):(.*)$", re.DOTALL)
_BRANCH_KEYWORD_RE = re.compile(r"^(plural|show):(.*)$", re.DOTALL)


def strip_tags(text: str) -> str:
    return _TAG_RE.sub("", text)


def split_top_level(text: str, sep: str) -> list[str]:
    """Split text on sep, ignoring occurrences nested inside {} or ()."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch in "{(":
            depth += 1
        elif ch in "})":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _find_top_level(text: str, target: str) -> int | None:
    depth = 0
    for i, ch in enumerate(text):
        if ch in "{(":
            depth += 1
        elif ch in "})":
            depth -= 1
        elif ch == target and depth == 0:
            return i
    return None


def placeholder_branches(body: str, unrecognized: list[str]) -> list[str]:
    """Return the literal-text branches a `{body}` placeholder can expand to.

    An empty list means the placeholder never contributes vocab text (it's a
    purely numeric or icon-glyph hole).
    """
    if ":" not in body:
        return []  # bare var: numeric value or a fixed icon glyph, no words

    _name, rest = body.split(":", 1)

    if _VALUE_ONLY_FORMATTERS.match(rest):
        return []
    if _ICON_FORMATTERS.match(rest):
        return []  # <ENERGY>/<STAR> are fixed symbol tokens, not scanned text

    m = _CHOOSE_RE.match(rest)
    if m:
        return split_top_level(m.group(2), "|")

    m = _BRANCH_KEYWORD_RE.match(rest)
    if m:
        return split_top_level(m.group(1), "|")

    if rest.startswith("cond:"):
        segments = split_top_level(rest[len("cond:"):], "|")
        branches = []
        for seg in segments:
            q = _find_top_level(seg, "?")
            branches.append(seg[q + 1 :] if q is not None else seg)
        return branches

    if "|" in rest:
        return split_top_level(rest, "|")

    unrecognized.append(body)
    return []


def normalize_and_split(text: str, *, split_digits: bool) -> list[str]:
    """Lowercase, strip punctuation, split hyphens, split on whitespace.

    split_digits=True (runtime tokenizer): each digit becomes its own token,
    e.g. "18" -> "1", "8" (TOKENIZER.md pipeline step 4).
    split_digits=False (vocab build): digit runs are dropped entirely, since
    the vocab only needs the closed mechanics-word class - digits 0-9 are
    already a fixed token class and don't need "discovering" from data.

    '%', '+', '.', ',', ':' are likewise fixed symbol tokens (TOKENIZER.md
    "Symbols"): isolated as their own tokens when split_digits=True, dropped
    entirely when building vocab words. The three punctuation marks carry
    real clause/sentence-boundary structure (unlike quotes/parens, which are
    purely decorative and are discarded by _PUNCT_RE above), so they're kept
    as tokens rather than stripped.

    Standalone capital "X" gets the same treatment, but must be pulled out
    *before* lowercasing (a sentinel byte survives .lower() unlike a letter
    would), or it's indistinguishable from the ordinary lowercase "x" used
    as a multiplier suffix.
    """
    text = text.replace("\n", " ")
    text = _X_VAR_RE.sub(_X_SENTINEL, text)
    text = text.lower()
    text = _PUNCT_RE.sub("", text)
    text = text.replace("-", " ")  # hyphenated words split on the hyphen
    if split_digits:
        text = _DIGIT_RUN_RE.sub(lambda m: " " + " ".join(m.group()) + " ", text)
        text = _SYMBOL_CHAR_RE.sub(lambda m: " " + m.group() + " ", text)
        text = text.replace(_X_SENTINEL, " X ")
    else:
        text = _DIGIT_RUN_RE.sub(" ", text)
        text = _SYMBOL_CHAR_RE.sub(" ", text)
        text = text.replace(_X_SENTINEL, " ")
    return [w for w in text.split() if w]


def collect_words(
    raw_text: str,
    words: set[str],
    unrecognized: list[str],
    substitute=lambda text: text,
) -> None:
    """Recursively scan a raw (unrendered) template string for vocab words.

    Expands every placeholder into all of its branches (collecting words
    from all of them, not just one), strips markup tags, and normalizes.

    `substitute` is applied to `raw_text` and to every branch before
    scanning - used to blank out entity-title references (see
    reference_lexicon.substitute_references) so they never become vocab
    words, without this module needing to know about the lexicon.
    """
    raw_text = substitute(raw_text)
    literal_chunks: list[str] = []
    i = 0
    n = len(raw_text)
    while i < n:
        ch = raw_text[i]
        if ch == "{":
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if raw_text[j] == "{":
                    depth += 1
                elif raw_text[j] == "}":
                    depth -= 1
                j += 1
            body = raw_text[i + 1 : j - 1]
            literal_chunks.append(" ")
            for branch in placeholder_branches(body, unrecognized):
                collect_words(branch, words, unrecognized, substitute)
            i = j
        else:
            literal_chunks.append(ch)
            i += 1
    literal_text = strip_tags("".join(literal_chunks))
    words.update(normalize_and_split(literal_text, split_digits=False))
