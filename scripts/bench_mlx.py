"""Benchmark MLX Whisper (Apple Silicon GPU) warm latency vs the clips."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mlx_whisper  # noqa: E402
from murti.audio_io import load_wav_16k_mono  # noqa: E402

REPO = "mlx-community/whisper-large-v3-turbo"
AUD = Path.home() / "dictation-app" / "tests" / "audio"
CLIPS = ["en", "hi", "hinglish"]


def transcribe(audio):
    return mlx_whisper.transcribe(audio, path_or_hf_repo=REPO)


def main():
    clips = {c: load_wav_16k_mono(str(AUD / f"{c}.wav")) for c in CLIPS}
    print("warming up (downloads model on first run)...")
    t0 = time.time()
    transcribe(clips["en"])  # warm-up + download
    print(f"warm-up+load: {time.time()-t0:.1f}s\n")
    for c in CLIPS:
        a = clips[c]
        dur = len(a) / 16000
        t0 = time.time()
        r = transcribe(a)
        el = time.time() - t0
        txt = r["text"].strip()
        print(f"{c:9s} {dur:.1f}s -> {el:5.2f}s ({dur/el:.2f}x RT) [{r.get('language')}] {txt[:50]}")


if __name__ == "__main__":
    main()
