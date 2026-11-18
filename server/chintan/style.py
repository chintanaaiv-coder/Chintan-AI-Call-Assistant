"""'Teach Chintan how I talk': examples from the owner's real calls.

The owner pastes transcripts (for example from iPhone call recordings in Notes).
Before saving, anything that looks like a number, PAN, Aadhaar, account, amount,
email or phone is blanked out, so Chintan can copy the owner's *way of talking*
but never repeat a client's details. For each call, the few examples most like
the current conversation go into the AI's instructions.
"""
from __future__ import annotations

import re

MAX_EXAMPLE_CHARS = 1500
EXAMPLES_PER_CALL = 3

_REDACTIONS = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[email]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.I), "[PAN]"),
    (re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", re.I), "[GSTIN]"),
    (re.compile(r"(?:₹|rs\.?|inr)\s*[\d,]+(?:\.\d+)?(?:\s*(?:lakh|lakhs|crore|crores|k))?", re.I), "[amount]"),
    (re.compile(r"\b[\d,]+(?:\.\d+)?\s*(?:lakh|lakhs|crore|crores)\b", re.I), "[amount]"),
    (re.compile(r"(?<!\w)\+?\d[\d\s-]{7,}\d(?!\w)"), "[number]"),  # phones, Aadhaar, account numbers
    (re.compile(r"\b\d{4,}\b"), "[number]"),                       # any other long number
]


def redact(text: str) -> str:
    for pattern, label in _REDACTIONS:
        text = pattern.sub(label, text)
    return text


def clean_example(text: str) -> str:
    text = redact(text.strip())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:MAX_EXAMPLE_CHARS]


_WORD = re.compile(r"[a-z]{3,}")
_STOP = {"the", "and", "you", "for", "are", "this", "that", "with", "have", "your", "will", "can", "not",
         "what", "about", "call", "calling", "hai", "hain", "aap", "kya", "nahi", "haan", "sir", "madam"}


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def pick_examples(examples: list[dict], conversation: str, k: int = EXAMPLES_PER_CALL) -> list[dict]:
    """The k examples sharing the most words with the conversation so far (newest first on ties)."""
    if not examples:
        return []
    now = _words(conversation)
    scored = sorted(examples, key=lambda e: (len(now & _words(e["title"] + " " + e["text"])), e["created_at"]),
                    reverse=True)
    return scored[:k]


def examples_prompt(owner_name: str, examples: list[dict]) -> str:
    if not examples:
        return ""
    blocks = "\n\n".join(f"--- Example: {e['title']} ---\n{e['text']}" for e in examples)
    return (f"\n\nHOW {owner_name.upper()} TALKS ON THE PHONE (excerpts from his real calls). Copy his tone, "
            f"phrases, politeness and Hindi/English mix. These are for STYLE ONLY: never repeat any name, fact, "
            f"figure or detail from them, and they never override the rules above.\n\n{blocks}")
