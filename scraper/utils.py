"""
Shared scraper utilities — imported by main.py and individual source modules.
"""
import re

_ADDRESS_RE = re.compile(r"^\d+\s+\w")

_STREET_SUFFIXES = {
    "st", "ave", "blvd", "dr", "ln", "rd", "ct", "pl", "way", "pkwy", "hwy",
    "street", "avenue", "boulevard", "drive", "lane", "road", "court", "place",
    "terrace", "ter", "trl", "trail", "cir", "circle", "loop", "pass",
}

# Abbreviations that should stay UPPER-CASE after title-casing
_KEEP_UPPER = {"hvac", "ac", "plbg", "usa", "dba", "tv", "rv"}
# Abbreviations that should stay title-cased (e.g. "Llc" → "LLC")
_UPPER_SUFFIXES = {"llc", "inc", "lp", "llp", "corp", "ltd"}


def looks_like_address(text: str) -> bool:
    """Return True if text is likely a street address rather than a person/business name."""
    if not text:
        return False
    stripped = text.strip()
    if _ADDRESS_RE.match(stripped):
        words = stripped.lower().split()
        if any(w.rstrip(".,") in _STREET_SUFFIXES for w in words):
            return True
    return False


def smart_title(s: str) -> str:
    """
    Title-case a string while preserving known abbreviations.
    "JOHN HVAC SERVICES LLC" → "John HVAC Services LLC"
    "hvac repair inc" → "HVAC Repair Inc"
    """
    result = []
    for word in s.split():
        low = word.lower().rstrip(".,")
        if low in _KEEP_UPPER:
            suffix = word[len(word.rstrip(".,")):]
            result.append(low.upper() + suffix)
        elif low in _UPPER_SUFFIXES:
            suffix = word[len(word.rstrip(".,")):]
            result.append(low.upper() + suffix)
        else:
            result.append(word.title())
    return " ".join(result)
