"""Usage insights + voice profile — computed and stored locally.

Persists to ~/.config/murti/insights.json. No network.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

INSIGHTS_PATH = Path.home() / ".config" / "murti" / "insights.json"
_WORD = re.compile(r"[^\s]+")
# Typing baseline used to estimate "time saved" vs speaking.
TYPING_WPM = 40.0


class Insights:
    def __init__(self, data: dict | None = None):
        d = data or {}
        self.total_words: int = d.get("total_words", 0)
        self.total_seconds: float = d.get("total_seconds", 0.0)
        self.sessions: int = d.get("sessions", 0)
        self.per_day: dict[str, int] = d.get("per_day", {})
        self.word_counts: Counter = Counter(d.get("word_counts", {}))

    # --------------------------------------------------------------- io
    @classmethod
    def load(cls, path: Path = INSIGHTS_PATH) -> "Insights":
        if path.exists():
            try:
                return cls(json.loads(path.read_text()))
            except Exception:  # noqa: BLE001
                pass
        return cls()

    def save(self, path: Path = INSIGHTS_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "total_words": self.total_words,
            "total_seconds": round(self.total_seconds, 2),
            "sessions": self.sessions,
            "per_day": self.per_day,
            "word_counts": dict(self.word_counts.most_common(200)),
        }, indent=2, ensure_ascii=False))

    # --------------------------------------------------------------- record
    def record(self, text: str, seconds: float, today: str | None = None) -> None:
        words = _WORD.findall(text or "")
        n = len(words)
        if n == 0:
            return
        self.total_words += n
        self.total_seconds += max(0.0, seconds)
        self.sessions += 1
        day = today or date.today().isoformat()
        self.per_day[day] = self.per_day.get(day, 0) + n
        for w in words:
            key = w.lower().strip(".,!?;:\"'()")
            if len(key) >= 3:
                self.word_counts[key] += 1

    # --------------------------------------------------------------- summary
    def wpm(self) -> float:
        mins = self.total_seconds / 60.0
        return round(self.total_words / mins, 0) if mins > 0 else 0.0

    def time_saved_hours(self) -> float:
        """Hours saved vs typing the same words at TYPING_WPM."""
        typed = self.total_words / TYPING_WPM            # minutes to type
        spoken = self.total_seconds / 60.0               # minutes spent speaking
        return round(max(0.0, typed - spoken) / 60.0, 1)

    def streak_days(self) -> int:
        from datetime import date as _d, timedelta
        d, n = _d.today(), 0
        while d.isoformat() in self.per_day:
            n += 1
            d -= timedelta(days=1)
        return n

    def summary(self) -> dict:
        return {
            "total_words": self.total_words,
            "wpm": self.wpm(),
            "time_saved_hours": self.time_saved_hours(),
            "streak_days": self.streak_days(),
            "sessions": self.sessions,
            "top_words": self.word_counts.most_common(8),
            "per_day": self.per_day,
        }
