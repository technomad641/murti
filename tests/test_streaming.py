"""Streaming transcriber: silence splitting, commit boundaries, full coverage.

Accuracy of real speech needs a live mic + model; here we verify the
deterministic machinery with synthetic audio and a fake STT engine.
"""
import numpy as np

from murti.streaming import StreamingTranscriber, find_silence_split

SR = 16_000


def loud(sec):
    t = np.linspace(0, sec, int(sec * SR), endpoint=False)
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def silence(sec):
    return np.zeros(int(sec * SR), dtype=np.float32)


class FakeEngine:
    """Counts samples seen so we can prove every sample is transcribed once."""

    def __init__(self):
        self.total = 0
        self.calls = 0

    def transcribe(self, audio):
        self.total += len(audio)
        self.calls += 1
        return f"[{len(audio)}]", "en"


# ---- silence detection -------------------------------------------------- #

def test_find_silence_split_lands_in_the_pause():
    audio = np.concatenate([loud(3), silence(1), loud(3)])
    i = find_silence_split(audio, SR, min_head_sec=2.5, min_tail_sec=1.0)
    assert i is not None
    assert 3.0 <= i / SR <= 4.0  # inside the 3–4s silent gap


def test_find_silence_split_none_without_a_pause():
    assert find_silence_split(loud(5), SR) is None


def test_find_silence_split_none_when_too_short():
    assert find_silence_split(loud(1), SR, min_head_sec=2.5, min_tail_sec=1.0) is None


# ---- commit logic (synchronous, no threads) ----------------------------- #

def test_no_commit_below_window():
    eng = FakeEngine()
    tx = StreamingTranscriber(eng, window_sec=6.0)
    tx._pending = loud(3)
    tx._maybe_commit()
    assert eng.calls == 0
    assert tx._committed == []


def test_commits_the_head_at_a_pause():
    eng = FakeEngine()
    tx = StreamingTranscriber(eng, window_sec=6.0, min_head_sec=2.5, min_tail_sec=1.0)
    tx._pending = np.concatenate([loud(4), silence(1.5), loud(4)])  # 9.5s
    before = len(tx._pending)
    tx._maybe_commit()
    assert eng.calls == 1
    assert len(tx._committed) == 1
    assert 0 < len(tx._pending) < before  # tail kept for the next pass


def test_forced_commit_when_no_pause_in_a_long_stretch():
    eng = FakeEngine()
    tx = StreamingTranscriber(eng, window_sec=6.0, max_window_sec=10.0)
    tx._pending = loud(12)  # no silence at all, past max_window
    tx._maybe_commit()
    assert eng.calls == 1  # cut at the window rather than wait forever


# ---- end-to-end coverage through the worker thread ---------------------- #

def test_finalize_transcribes_every_sample_once():
    eng = FakeEngine()
    tx = StreamingTranscriber(eng, window_sec=6.0)
    tx.start()
    total = 0
    for seg in (loud(2), silence(1), loud(2)):  # 5s total, under one window
        tx.feed(seg)
        total += len(seg)
    text, lang = tx.finalize()
    assert eng.total == total  # no audio dropped, none double-counted
    assert text and lang == "en"


def test_streamed_long_audio_is_fully_covered():
    eng = FakeEngine()
    tx = StreamingTranscriber(eng, window_sec=6.0, min_head_sec=2.5, min_tail_sec=1.0)
    tx.start()
    total = 0
    for seg in (loud(4), silence(1.5), loud(4), silence(1.5), loud(3)):
        tx.feed(seg)
        total += len(seg)
    text, _ = tx.finalize()
    assert eng.total == total  # every sample transcribed exactly once
    assert text
