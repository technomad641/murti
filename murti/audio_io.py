"""Audio loading helpers.

Whisper wants mono float32 PCM at 16 kHz. We load WAV files with soundfile
and (if needed) downmix to mono. Resampling is handled upstream by ffmpeg for
file tests, and by capturing at 16 kHz directly for live recording, so this
module intentionally does not resample.
"""
from __future__ import annotations

import numpy as np
import soundfile as sf

TARGET_SR = 16000


def load_wav_16k_mono(path: str) -> np.ndarray:
    """Load a 16 kHz WAV as mono float32 in [-1, 1]. Raises if sample rate != 16k."""
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    if sr != TARGET_SR:
        raise ValueError(
            f"{path} is {sr} Hz; expected {TARGET_SR}. "
            "Convert first: ffmpeg -i in -ar 16000 -ac 1 out.wav"
        )
    mono = data.mean(axis=1)  # downmix any channel count to mono
    return np.ascontiguousarray(mono, dtype=np.float32)
