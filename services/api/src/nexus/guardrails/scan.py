"""Scans run on every uploaded document before the AI can read it.

Hidden instructions: text written to steer an AI ("ignore your previous
instructions…"), whether planted deliberately or pasted by accident. The
agents are always told that document text is evidence, never instructions;
this scan additionally tells the lawyer the document contains such text.

Sensitive numbers: identifiers that usually should not be in a matter file
by accident (social security numbers, payment cards, Indian PAN/Aadhaar,
IBANs). Flagged so a person can decide; nothing is removed automatically.
"""

import re
from dataclasses import dataclass, field

_INJECTION = [
    (re.compile(p, re.IGNORECASE), label)
    for p, label in [
        (r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|all|any)\b.{0,20}\b(instructions?|prompts?|rules|directions)\b", "asks the AI to ignore its instructions"),
        (r"\b(system|developer)\s+(prompt|message|instructions?)\b", "refers to the AI's system prompt"),
        (r"\byou\s+are\s+(now\s+)?(an?\s+)?(ai|assistant|language model|chatbot|llm|claude|gpt)\b", "tries to redefine the AI's role"),
        (r"\b(as an ai|as a language model)\b", "addresses an AI directly"),
        (r"\b(do not|don't|never)\s+(tell|inform|mention|reveal|disclose)\b.{0,30}\b(user|lawyer|reader|attorney|anyone)\b", "tells the AI to hide something from the reader"),
        (r"\b(respond|reply|answer|output)\s+only\s+with\b", "dictates what the AI should answer"),
        (r"<\|?(im_start|im_end|system|endoftext)\|?>|\[/?INST\]", "contains AI control tokens"),
    ]
]


def _luhn(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _cards(text: str) -> int:
    count = 0
    for match in re.finditer(r"\b(?:\d[ -]?){13,19}\b", text):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn(digits) and len(set(digits)) > 1:
            count += 1
    return count


_SENSITIVE = [
    ("US social security number", lambda t: len(re.findall(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b", t))),
    ("payment card number", _cards),
    ("Indian PAN", lambda t: len(re.findall(r"\b[A-Z]{3}[PCHABGJLFT][A-Z]\d{4}[A-Z]\b", t))),
    ("Aadhaar number", lambda t: len(re.findall(r"\b[2-9]\d{3}\s\d{4}\s\d{4}\b", t))),
    ("IBAN", lambda t: len(re.findall(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b", t))),
]


@dataclass
class ScanResult:
    hidden_instructions: list[dict] = field(default_factory=list)
    sensitive: dict[str, int] = field(default_factory=dict)

    def as_flags(self) -> dict:
        return {
            "hidden_instructions": self.hidden_instructions[:20],
            "hidden_instruction_count": len(self.hidden_instructions),
            "sensitive": self.sensitive,
        }


def scan(passages: list[tuple[int, int, str]]) -> ScanResult:
    """`passages` is (seq, page, text)."""
    result = ScanResult()
    for seq, page, text in passages:
        for pattern, label in _INJECTION:
            match = pattern.search(text)
            if match:
                start = max(0, match.start() - 60)
                result.hidden_instructions.append(
                    {"seq": seq, "page": page, "why": label,
                     "excerpt": text[start : match.end() + 60].strip()}
                )
                break
        for label, counter in _SENSITIVE:
            n = counter(text)
            if n:
                result.sensitive[label] = result.sensitive.get(label, 0) + n
    return result
