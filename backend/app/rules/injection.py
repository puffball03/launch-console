import re
import unicodedata

# Phrases that address the system rather than describe an anomaly. Each is a backstop to
# the model's injection check: a match flags the report for human review. Neither this
# nor the model check can change the verdict, which comes only from rules/limits.py.
PATTERNS: dict[str, re.Pattern[str]] = {
    # "system:" starting a sentence or clause (any case), or an all-caps "SYSTEM:" anywhere.
    # "Propulsion system: nominal" stays clean because "system" follows a word there.
    "system prefix": re.compile(r"(?i:(?:^|[.!?\n,;<])\s*system\s*:)|\bSYSTEM\s*:"),
    "ignore instructions": re.compile(
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?"
        r"(?:previous\s+|prior\s+|above\s+|earlier\s+|preceding\s+)?"
        r"(?:instructions|rules|limits|prompts?)\b",
        re.IGNORECASE,
    ),
    "role override": re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    "set verdict": re.compile(r"\b(?:set|change|mark|make)\s+(?:the\s+)?verdict\b", re.IGNORECASE),
    "approve request": re.compile(r"\bapprove\s+(?:this|it|the\s+briefing|immediately)\b", re.IGNORECASE),
    "override limits": re.compile(r"\boverride\s+(?:the\s+)?(?:limits?|verdict|rules)\b", re.IGNORECASE),
    "fake tag": re.compile(r"<\s*/?\s*(?:system|instructions?|assistant)\s*>", re.IGNORECASE),
    "new instructions": re.compile(r"\bnew\s+instructions\b", re.IGNORECASE),
}


ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))


def normalise(note: str) -> str:
    """Fold look-alike characters (full-width letters, ligatures) and drop invisible ones,
    so spacing tricks can't hide a phrase from the patterns."""
    return unicodedata.normalize("NFKC", note).translate(ZERO_WIDTH)


def prescreen(note: str) -> list[str]:
    """Names of the instruction-like patterns found in the note, in a fixed order."""
    text = normalise(note)
    return [name for name, pattern in PATTERNS.items() if pattern.search(text)]
