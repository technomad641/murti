"""Benchmark warm, in-process transcription latency with tuning knobs.

Mirrors the real app: load the model ONCE, then transcribe repeatedly.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from faster_whisper import WhisperModel  # noqa: E402
from murti.audio_io import load_wav_16k_mono  # noqa: E402

AUD = Path.home() / "dictation-app" / "tests" / "audio"
CLIPS = ["en", "hi", "hinglish"]


def run(model_name: str, beam_size: int, cpu_threads: int):
    print(f"\n=== model={model_name} beam={beam_size} threads={cpu_threads} ===")
    t0 = time.time()
    model = WhisperModel(
        model_name, device="cpu", compute_type="int8", cpu_threads=cpu_threads
    )
    print(f"load: {time.time()-t0:.1f}s")
    audios = {c: load_wav_16k_mono(str(AUD / f"{c}.wav")) for c in CLIPS}
    # warm-up pass (first inference pays lazy init)
    list(model.transcribe(audios["en"], beam_size=beam_size, vad_filter=True)[0])
    for c in CLIPS:
        a = audios[c]
        dur = len(a) / 16000
        t0 = time.time()
        segs, info = model.transcribe(a, beam_size=beam_size, vad_filter=True)
        text = "".join(s.text for s in segs).strip()
        el = time.time() - t0
        print(f"{c:9s} {dur:4.1f}s audio -> {el:5.2f}s  ({dur/el:4.2f}x RT)  [{info.language}] {text[:48]}")


if __name__ == "__main__":
    cores = os.cpu_count() or 8
    run("large-v3-turbo", beam_size=1, cpu_threads=cores)
