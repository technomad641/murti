"""Headless end-to-end test: wav -> transcribe -> postprocess -> final text.

Exercises the real Pipeline (minus GUI and paste) across settings variants.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from murti.audio_io import load_wav_16k_mono  # noqa: E402
from murti.config import Settings  # noqa: E402
from murti.pipeline import Pipeline  # noqa: E402

AUD = Path.home() / "dictation-app" / "tests" / "audio"
CLIPS = ["en", "hi", "hinglish"]


def run(label: str, settings: Settings):
    print(f"\n########## {label} "
          f"(engine={settings.engine}, translate={settings.translate_enabled}, "
          f"script={settings.hindi_script}, target={settings.target_language}) ##########")
    pipe = Pipeline(settings)
    for c in CLIPS:
        audio = load_wav_16k_mono(str(AUD / f"{c}.wav"))
        final, raw = pipe.process_audio(audio)
        print(f"[{c}]")
        print(f"   raw  : {raw}")
        print(f"   final: {final}")


if __name__ == "__main__":
    run("transcribe + romanized Hinglish (offline post)",
        Settings(translate_enabled=False, hindi_script="romanized"))
    run("transcribe + devanagari (no post)",
        Settings(translate_enabled=False, hindi_script="devanagari", online_cleanup=False))
