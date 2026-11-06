"""Citation check shared by extraction and analysis: a quote must exist in the cited clause."""

import re
import unicodedata

from rapidfuzz import fuzz

SEUIL = 90  # rapidfuzz score, 0-100


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("’", "'").replace("‘", "'").replace("«", '"').replace("»", '"')
    text = re.sub(r"-\s*\n\s*", "", text)  # hyphenation across lines
    return " ".join(re.sub(r"[^\w'\"%€]+", " ", text).split())


def citation_ok(extrait: str, texte_clause: str) -> bool:
    """Exact (normalised) match, or a fuzzy match covering a long enough quote."""
    q, t = normalise(extrait), normalise(texte_clause)
    if len(q) < 8:
        return False
    if q in t:
        return True
    return fuzz.partial_ratio(q, t) >= SEUIL
