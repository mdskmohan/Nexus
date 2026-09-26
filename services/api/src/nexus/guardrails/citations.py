"""Citation checking: the rule that nothing unverified reaches a lawyer.

A citation is a passage id plus a quote. It is verified only if the quote
appears, word for word, in that passage. Differences that are not differences
in wording — curly vs straight quotes, dash styles, line breaks, letter case —
are ignored. A quote may skip text with an ellipsis ("…" or "..."), in which
case each fragment must appear, in order.
"""

import re
import unicodedata
from dataclasses import dataclass

MIN_QUOTE_CHARS = 12

_TRANSLATE = str.maketrans(
    {
        "‘": "'", "’": "'", "‚": "'", "‛": "'",
        "“": '"', "”": '"', "„": '"', "‟": '"',
        "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
        " ": " ", "­": "",
    }
)
_ELLIPSIS = re.compile(r"\s*(?:\.\s?\.\s?\.|…)\s*")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE)
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)  # hyphenation across line breaks
    return re.sub(r"\s+", " ", text).strip().lower()


@dataclass
class Check:
    ok: bool
    reason: str = ""


def verify_quote(quote: str, passage_text: str) -> Check:
    fragments = [normalize(f) for f in _ELLIPSIS.split(quote) if normalize(f)]
    if not fragments:
        return Check(False, "The citation has no quoted text.")
    if sum(len(f) for f in fragments) < MIN_QUOTE_CHARS:
        return Check(False, "The quoted text is too short to show where the statement comes from.")
    haystack = normalize(passage_text)
    position = 0
    for fragment in fragments:
        found = haystack.find(fragment, position)
        if found < 0:
            return Check(False, "The quoted words do not appear in the cited passage.")
        position = found + len(fragment)
    return Check(True)
