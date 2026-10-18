"""Microphone capture at 16 kHz mono float32 (what Whisper expects).

Toggle model: start() opens a stream and accumulates audio; stop() returns the
captured signal as a single numpy array.
"""
from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class Recorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self.recording = False

    def _callback(self, indata, frames, time_info, status):  # noqa: ANN001
        if status:
            # Overflows etc. are non-fatal; keep going.
            pass
        with self._lock:
            self._frames.append(indata.copy().reshape(-1))

    def start(self) -> None:
        if self.recording:
            return
        with self._lock:
            self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()
        self.recording = True

    def stop(self) -> np.ndarray:
        """Stop recording and return mono float32 audio (empty array if none)."""
        if not self.recording:
            return np.zeros(0, dtype=np.float32)
        self.recording = False
        assert self._stream is not None
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._lock:
            if not self._frames:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._frames).astype(np.float32)
            self._frames = []
        return audio
