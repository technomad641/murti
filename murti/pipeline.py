"""The dictation pipeline: audio -> transcript -> shaped text -> inserted."""
from __future__ import annotations

import numpy as np

from . import postprocess
from .config import Settings
from .stt import make_engine
from .vocabulary import Dictionary
from .insights import Insights

SAMPLE_RATE = 16_000


class Pipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = make_engine(settings.engine, settings.model_name)
        self.dictionary = Dictionary.load()
        self.insights = Insights.load()

    def shape_text(self, raw: str, lang: str | None, audio_secs: float) -> str:
        """Turn a raw transcript into finished text (punctuation, romanization,
        dictionary) and record local insights. Shared by the whole-clip and
        streaming paths so post-processing always runs once, on the full text."""
        final = postprocess.process(raw, lang, self.settings)
        # personal dictionary: fix known spellings / casing, then learn new terms
        final = self.dictionary.apply(final)
        if self.settings.auto_learn and final:
            if self.dictionary.learn_from(final):
                self.dictionary.save()
        # usage insights (local)
        if final:
            self.insights.record(final, audio_secs)
            self.insights.save()
        return final

    def process_audio(self, audio: np.ndarray) -> tuple[str, str]:
        """Return (final_text, raw_transcript). Empty strings if no speech."""
        if audio is None or len(audio) == 0:
            return "", ""
        raw, lang = self.engine.transcribe(audio)
        final = self.shape_text(raw, lang, len(audio) / SAMPLE_RATE)
        return final, raw

    @staticmethod
    def _insert(final: str) -> None:
        from . import inserter  # imported here so headless tests don't need AppKit

        inserter.insert_text(final)

    def dictate(self, audio: np.ndarray, insert: bool = True) -> str:
        """Full flow: transcribe, shape, and (optionally) paste into focused app."""
        final, _ = self.process_audio(audio)
        if insert and final:
            self._insert(final)
        return final

    def dictate_streamed(
        self, raw: str, lang: str | None, audio_secs: float, insert: bool = True
    ) -> str:
        """Finish a streamed dictation: shape the already-transcribed text and
        (optionally) paste it. Only the short tail was left to transcribe, so
        this returns almost immediately after you stop."""
        final = self.shape_text(raw, lang, audio_secs)
        if insert and final:
            self._insert(final)
        return final
