"""Split page text into passages: the unit the AI searches, reads and cites.

A passage is roughly one clause or paragraph. Each carries the nearest
heading above it, so "Section 9 — Termination" travels with its text.
"""

import re
from dataclasses import dataclass

from nexus.ingest.extract import Page

TARGET_CHARS = 1200
MAX_CHARS = 2000

# Lines that start a new clause in contracts and pleadings.
_CLAUSE_START = re.compile(
    r"^\s*("
    r"(ARTICLE|Article|SECTION|Section|Clause|CLAUSE|Schedule|SCHEDULE|Exhibit|EXHIBIT)\s+[\dIVXLC]+"
    r"|\d{1,2}(\.\d{1,2}){0,3}\.?\s+[A-Z(]"
    r"|\([a-z]{1,3}\)\s"
    r"|\([ivx]{1,5}\)\s"
    r"|[A-Z][A-Z0-9 ,;:&'\-]{6,}$"
    r")"
)
_HEADING = re.compile(
    r"^\s*((ARTICLE|Article|SECTION|Section)\s+[\dIVXLC]+.*|\d{1,2}(\.\d{1,2})?\.?\s+[A-Z][^.]{2,80}\.?|[A-Z][A-Z0-9 ,;:&'\-]{6,80})\s*$"
)
_SENTENCE_END = re.compile(r"(?<=[.;:])\s+(?=[A-Z(\"“])")


@dataclass
class Passage:
    seq: int
    page: int
    heading: str
    text: str


def _paragraphs(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join words hyphenated across lines
    paragraphs: list[str] = []
    current: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if current and _CLAUSE_START.match(stripped):
            paragraphs.append(" ".join(current))
            current = []
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))
    return [re.sub(r"\s+", " ", p).strip() for p in paragraphs if p.strip()]


def _split_long(paragraph: str) -> list[str]:
    if len(paragraph) <= MAX_CHARS:
        return [paragraph]
    pieces, current = [], ""
    for sentence in _SENTENCE_END.split(paragraph):
        if current and len(current) + len(sentence) + 1 > TARGET_CHARS:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    # A single sentence longer than MAX_CHARS is hard-wrapped at a word boundary.
    out: list[str] = []
    for piece in pieces:
        while len(piece) > MAX_CHARS:
            cut = piece.rfind(" ", 0, MAX_CHARS)
            cut = cut if cut > 0 else MAX_CHARS
            out.append(piece[:cut].strip())
            piece = piece[cut:].strip()
        out.append(piece)
    return out


def chunk(pages: list[Page]) -> list[Passage]:
    passages: list[Passage] = []
    heading = ""
    for page in pages:
        buffer = ""
        for paragraph in _paragraphs(page.text):
            if _HEADING.match(paragraph) and len(paragraph) <= 90:
                if buffer:
                    passages.append(Passage(len(passages), page.number, heading, buffer))
                    buffer = ""
                heading = paragraph.rstrip(".")
                continue
            for piece in _split_long(paragraph):
                # Short neighbouring paragraphs are merged so a passage has enough context.
                if buffer and len(buffer) + len(piece) + 1 > TARGET_CHARS:
                    passages.append(Passage(len(passages), page.number, heading, buffer))
                    buffer = piece
                else:
                    buffer = f"{buffer}\n{piece}".strip()
        if buffer:
            passages.append(Passage(len(passages), page.number, heading, buffer))
    return passages
