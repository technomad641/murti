"""Headless tests for the local-real features (no mic, no network, no system)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from murti.vocabulary import Dictionary  # noqa: E402
from murti.insights import Insights  # noqa: E402
from murti.media import MediaController  # noqa: E402
from murti import devices  # noqa: E402


# ------------------------------------------------------------- vocabulary
def test_dictionary_learns_custom_words():
    d = Dictionary()
    learned = d.learn_from("I met Rajat about the Kubernetes rollout at Anthropic")
    assert "Rajat" in d.terms and "Kubernetes" in d.terms and "Anthropic" in d.terms
    assert "about" not in d.terms  # stop word
    assert set(learned) >= {"Rajat", "Kubernetes", "Anthropic"}


def test_dictionary_apply_corrections_and_casing():
    d = Dictionary(terms={"Anthropic"}, corrections={"hinglish": "Hinglish"})
    out = d.apply("i write hinglish at anthropic")
    assert "Hinglish" in out
    assert "Anthropic" in out  # casing snapped to custom term


def test_dictionary_roundtrip(tmp_path):
    p = tmp_path / "dict.json"
    d = Dictionary(terms={"Figma"}, corrections={"okr": "OKR"})
    d.save(p)
    d2 = Dictionary.load(p)
    assert "Figma" in d2.terms and d2.corrections["okr"] == "OKR"


# ------------------------------------------------------------- insights
def test_insights_record_and_summary():
    ins = Insights()
    ins.record("hello world this is a test", seconds=3.0, today="2026-10-17")
    ins.record("another dictation session here", seconds=2.0, today="2026-10-17")
    s = ins.summary()
    assert s["total_words"] == 10
    assert s["sessions"] == 2
    assert s["wpm"] > 0
    assert s["per_day"]["2026-10-17"] == 10
    assert isinstance(s["top_words"], list)


def test_insights_time_saved_nonnegative():
    ins = Insights()
    ins.record("word " * 100, seconds=30.0, today="2026-10-17")
    assert ins.time_saved_hours() >= 0


# ------------------------------------------------------------- media (injected)
def test_media_pause_resume_uses_runner():
    calls = []
    m = MediaController(runner=lambda s: calls.append(s) or "")
    m.pause_media()
    m.resume_media()
    assert any("pause" in c for c in calls)
    assert any("play" in c for c in calls)


def test_media_duck_saves_and_restores_volume():
    log = []

    def runner(script):
        log.append(script)
        return "50" if "get volume settings" in script else ""

    m = MediaController(runner=runner)
    m.duck_audio()
    assert any("output volume 0" in s for s in log)
    m.restore_audio()
    assert any("output volume 50" in s for s in log)


def test_media_restore_without_duck_is_noop():
    m = MediaController(runner=lambda s: "")
    m.restore_audio()  # should not raise


# ------------------------------------------------------------- devices
def test_is_headset_matches_known_brands():
    assert devices.is_headset("Jabra Evolve2 65")
    assert devices.is_headset("AirPods Pro")
    assert not devices.is_headset("MacBook Pro Microphone")


def test_detect_headset_from_list():
    devs = [{"name": "Built-in", "headset": False},
            {"name": "Jabra", "headset": True}]
    assert devices.detect_headset(devs)["name"] == "Jabra"
