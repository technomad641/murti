"""Streaming transcription — transcribe while you speak, so stopping is instant.

The naive flow records until you stop, then transcribes the whole clip, so the
wait after you release the key grows with how long you spoke. This transcribes
microphone audio in near-real-time on a background worker and commits finished
words at natural pauses (silence). When you stop, only the short trailing
segment is left to transcribe — turning the post-stop wait from
O(length-of-dictation) into O(a-few-seconds), regardless of how long you talked.

Only speech-to-text runs per chunk here; the raw transcript is shaped once
(punctuation, romanization, dictionary) by the pipeline at finalize.
"""
from __future__ import annotations

import queue
import threading

import numpy as np

SAMPLE_RATE = 16_000


def frame_rms(audio: np.ndarray, sr: int, frame_ms: float = 30.0):
    """RMS energy per fixed-size frame. Returns (rms_per_frame, hop_samples)."""
    hop = max(1, int(sr * frame_ms / 1000.0))
    n = len(audio) // hop
    if n == 0:
        return np.zeros(0, dtype=np.float64), hop
    block = audio[: n * hop].astype(np.float64).reshape(n, hop)
    return np.sqrt(np.mean(block * block, axis=1)), hop


def find_silence_split(
    audio: np.ndarray,
    sr: int = SAMPLE_RATE,
    min_head_sec: float = 2.5,
    min_tail_sec: float = 1.0,
    frame_ms: float = 30.0,
    rel_thresh: float = 0.2,
    abs_floor: float = 1e-3,
) -> int | None:
    """Sample index at a clear pause, or None if there isn't one yet.

    The split must leave at least ``min_head_sec`` of audio before it (so we
    commit a meaningful amount) and ``min_tail_sec`` after it (so we never cut
    the just-spoken, possibly-unfinished word). Among qualifying silent frames
    the quietest is chosen — the most confident pause.
    """
    rms, hop = frame_rms(audio, sr, frame_ms)
    if len(rms) == 0:
        return None
    peak = float(rms.max())
    thresh = max(abs_floor, peak * rel_thresh)
    lo = int(min_head_sec * sr / hop)
    hi = len(rms) - int(min_tail_sec * sr / hop)
    if hi <= lo:
        return None
    region = rms[lo:hi]
    quiet = np.where(region <= thresh)[0]
    if len(quiet) == 0:
        return None
    best = lo + int(quiet[np.argmin(region[quiet])])
    return best * hop


class StreamingTranscriber:
    """Feed it mic chunks while recording; call finalize() when you stop.

    ``feed`` is realtime-safe (it only enqueues). A worker thread accumulates
    audio and commits transcribed text at silence boundaries. Short dictations
    (shorter than one window) simply transcribe once at finalize — identical to
    the non-streaming path, with no added latency.
    """

    def __init__(
        self,
        engine,
        sr: int = SAMPLE_RATE,
        window_sec: float = 6.0,
        max_window_sec: float = 15.0,
        min_head_sec: float = 2.5,
        min_tail_sec: float = 1.0,
    ):
        self.engine = engine
        self.sr = sr
        self.window = int(window_sec * sr)
        self.max_window = int(max_window_sec * sr)
        self.min_head_sec = min_head_sec
        self.min_tail_sec = min_tail_sec

        self._q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._pending = np.zeros(0, dtype=np.float32)
        self._committed: list[str] = []
        self._last_lang: str | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None

    # ---- lifecycle -------------------------------------------------------
    def start(self) -> None:
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def feed(self, chunk: np.ndarray) -> None:
        """Enqueue mic audio. Safe to call from the realtime audio callback."""
        self._q.put(np.asarray(chunk, dtype=np.float32).reshape(-1))

    def finalize(self) -> tuple[str, str | None]:
        """Stop, transcribe the remaining tail, and return (raw_text, lang)."""
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=10.0)
            self._worker = None
        self._drain(block=False)
        if len(self._pending) > 0:
            self._transcribe_commit(self._pending)
            self._pending = np.zeros(0, dtype=np.float32)
        with self._lock:
            text = " ".join(t.strip() for t in self._committed if t.strip())
            lang = self._last_lang
        return text.strip(), lang

    # ---- internals -------------------------------------------------------
    def _drain(self, block: bool, timeout: float | None = None) -> None:
        """Move everything currently queued into the pending buffer."""
        try:
            first = self._q.get(block=block, timeout=timeout)
        except queue.Empty:
            return
        chunks = [self._pending, first]
        while True:
            try:
                chunks.append(self._q.get_nowait())
            except queue.Empty:
                break
        self._pending = np.concatenate(chunks)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._drain(block=True, timeout=0.1)
            self._maybe_commit()

    def _maybe_commit(self) -> None:
        if len(self._pending) < self.window:
            return
        split = find_silence_split(
            self._pending, self.sr, self.min_head_sec, self.min_tail_sec
        )
        if split is None:
            if len(self._pending) < self.max_window:
                return  # keep waiting for a natural pause
            split = self.window  # no pause in a long stretch — cut at the window
        head, self._pending = self._pending[:split], self._pending[split:]
        self._transcribe_commit(head)

    def _transcribe_commit(self, audio: np.ndarray) -> None:
        if audio is None or len(audio) == 0:
            return
        try:
            text, lang = self.engine.transcribe(audio)
        except Exception:  # noqa: BLE001 — a bad chunk must not kill the stream
            return
        if text and text.strip():
            with self._lock:
                self._committed.append(text.strip())
                if lang:
                    self._last_lang = lang
