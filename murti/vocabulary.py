"""Personal dictionary: auto-learn words you dictate and fix known spellings.

Local-only. Persists to ~/.config/murti/dictionary.json. No network.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DICT_PATH = Path.home() / ".config" / "murti" / "dictionary.json"

# Words the recognizer would never need help with — don't "learn" these.
_STOP = {
    "the", "and", "for", "that", "this", "with", "you", "your", "are", "was",
    "have", "has", "had", "will", "would", "could", "should", "from", "they",
    "them", "then", "than", "what", "when", "where", "which", "who", "why",
    "how", "about", "there", "their", "here", "okay", "yeah",
}
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")


class Dictionary:
    def __init__(self, terms=None, corrections=None):
        # terms: set of custom words to protect/recognize
        self.terms: set[str] = set(terms or [])
        # corrections: {wrong_lowercase: right_spelling}
        self.corrections: dict[str, str] = dict(corrections or {})

    # --------------------------------------------------------------- io
    @classmethod
    def load(cls, path: Path = DICT_PATH) -> "Dictionary":
        if path.exists():
            try:
                d = json.loads(path.read_text())
                return cls(d.get("terms"), d.get("corrections"))
            except Exception:  # noqa: BLE001
                pass
        return cls()

    def save(self, path: Path = DICT_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"terms": sorted(self.terms), "corrections": self.corrections},
            indent=2, ensure_ascii=False))

    # --------------------------------------------------------------- edit
    def add(self, word: str) -> None:
        w = word.strip()
        if w:
            self.terms.add(w)

    def add_correction(self, wrong: str, right: str) -> None:
        if wrong.strip() and right.strip():
            self.corrections[wrong.strip().lower()] = right.strip()

    def learn_from(self, text: str, min_len: int = 4) -> list[str]:
        """Auto-add candidate custom words from dictated text.

        Heuristic: capitalized-mid-sentence tokens and CamelCase/ALLCAPS
        identifiers that aren't common English. Returns the newly learned ones.
        """
        learned: list[str] = []
        tokens = _WORD.findall(text)
        for i, tok in enumerate(tokens):
            low = tok.lower()
            if low in _STOP or len(tok) < min_len:
                continue
            mid_sentence_cap = tok[0].isupper() and i > 0
            camel = any(c.isupper() for c in tok[1:])
            allcaps = tok.isupper() and len(tok) >= 3
            if (mid_sentence_cap or camel or allcaps) and tok not in self.terms:
                self.terms.add(tok)
                learned.append(tok)
        return learned

    # --------------------------------------------------------------- apply
    def apply(self, text: str) -> str:
        """Fix known mis-spellings and snap casing to custom terms."""
        if not text:
            return text
        out = text
        # explicit corrections (whole-word, case-insensitive)
        for wrong, right in self.corrections.items():
            out = re.sub(rf"\b{re.escape(wrong)}\b", right, out, flags=re.IGNORECASE)
        # casing: ensure custom terms keep their canonical capitalization
        for term in self.terms:
            out = re.sub(rf"\b{re.escape(term)}\b", term, out, flags=re.IGNORECASE)
        return out
