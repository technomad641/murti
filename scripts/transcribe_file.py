"""Transcribe a 16 kHz mono WAV file and print the result.

Usage: python scripts/transcribe_file.py <file.wav> [model_name]
Used to validate the STT stage without a live microphone.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from murti.audio_io import load_wav_16k_mono  # noqa: E402
from murti.stt import DEFAULT_MODEL, load_model, transcribe  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    wav = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL

    print(f"[1/3] loading model '{model_name}' (first run downloads weights)...")
    t0 = time.time()
    model = load_model(model_name)
    print(f"      model ready in {time.time() - t0:.1f}s")

    print(f"[2/3] loading audio {wav} ...")
    audio = load_wav_16k_mono(wav)
    dur = len(audio) / 16000
    print(f"      {dur:.1f}s of audio")

    print("[3/3] transcribing ...")
    t0 = time.time()
    text, info = transcribe(audio, model=model)
    elapsed = time.time() - t0
    print("-" * 60)
    print(f"detected language : {info.language} (p={info.language_probability:.2f})")
    print(f"transcribe time   : {elapsed:.1f}s  ({dur / elapsed:.1f}x realtime)")
    print(f"text              : {text}")
    print("-" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
