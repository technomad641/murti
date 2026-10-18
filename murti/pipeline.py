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

    def process_audio(self, audio: np.ndarray) -> tuple[str, str]:
        """Return (final_text, raw_transcript). Empty strings if no speech."""
        if audio is None or len(audio) == 0:
            return "", ""
        raw, lang = self.engine.transcribe(audio)
        final = postprocess.process(raw, lang, self.settings)
        # personal dictionary: fix known spellings / casing, then learn new terms
        final = self.dictionary.apply(final)
        if self.settings.auto_learn and final:
            if self.dictionary.learn_from(final):
                self.dictionary.save()
        # usage insights (local)
        if final:
            secs = len(audio) / SAMPLE_RATE
            self.insights.record(final, secs)
            self.insights.save()
        return final, raw

    def dictate(self, audio: np.ndarray, insert: bool = True) -> str:
        """Full flow: transcribe, shape, and (optionally) paste into focused app."""
        final, _ = self.process_audio(audio)
        if insert and final:
            from . import inserter  # imported here so headless tests don't need AppKit

            inserter.insert_text(final)
        return final
