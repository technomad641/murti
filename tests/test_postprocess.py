"""Headless unit tests for text post-processing (no model, no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from murti import postprocess as pp  # noqa: E402
from murti.config import Settings  # noqa: E402


def test_has_devanagari():
    assert pp.has_devanagari("नमस्ते")
    assert pp.has_devanagari("hello मेरा")
    assert not pp.has_devanagari("hello world")
    assert not pp.has_devanagari("")


def test_romanize_schwa_deletion():
    # नाम -> "naam" not "nama"; कल -> "kal" not "kala"
    out = pp.romanize_offline("मेरा नाम राजत है")
    assert "nama " not in out and "naam" in out
    assert "raajat" in out or "rajat" in out
    assert not pp.has_devanagari(out)


def test_romanize_passes_english_through():
    assert pp.romanize_offline("hello world") == "hello world"


def test_romanize_anusvara_nasal():
    # ं -> "n" generally (velar/dental context), not "m"
    assert "meeting" in pp.romanize_offline("मीटिंग")
    out = pp.romanize_offline("अटेंड")
    assert "atend" in out and "atemd" not in out


def test_romanize_no_stray_itrans_markers():
    out = pp.romanize_offline("अपडेट प्रोजेक्ट")
    assert "." not in out  # nukta dots stripped
    assert "~" not in out and "^" not in out


def test_process_english_transcribe_mode_no_network():
    s = Settings(translate_enabled=False, hindi_script="romanized", online_cleanup=False)
    assert pp.process("Hello there.", "en", s) == "Hello there."


def test_process_devanagari_mode_keeps_script():
    s = Settings(translate_enabled=False, hindi_script="devanagari", online_cleanup=False)
    txt = "मेरा नाम राजत है"
    assert pp.process(txt, "hi", s) == txt


def test_process_romanized_mode_offline():
    s = Settings(translate_enabled=False, hindi_script="romanized", online_cleanup=False)
    out = pp.process("मेरा नाम राजत है", "hi", s)
    assert not pp.has_devanagari(out)


def test_process_empty():
    s = Settings()
    assert pp.process("", "en", s) == ""
    assert pp.process("   ", None, s) == ""


def test_romanize_if_hindi_target_converts(monkeypatch):
    s = Settings(target_language="Hindi", hindi_script="romanized")
    out = pp._romanize_if_hindi_target("मेरा नाम", s)
    assert not pp.has_devanagari(out)


def test_romanize_if_hindi_target_devanagari_kept():
    s = Settings(target_language="Hindi", hindi_script="devanagari")
    txt = "मेरा नाम"
    assert pp._romanize_if_hindi_target(txt, s) == txt


def test_romanize_if_english_target_untouched():
    s = Settings(target_language="English", hindi_script="romanized")
    assert pp._romanize_if_hindi_target("hello", s) == "hello"


def test_translate_uses_offline_when_no_claude(monkeypatch):
    monkeypatch.setattr(pp, "_claude", lambda *a, **k: None)
    import murti.translate_offline as to
    monkeypatch.setattr(to, "translate", lambda text, src, tgt: "TRANSLATED")
    s = Settings(translate_enabled=True, target_language="English")
    assert pp.process("नमस्ते", "hi", s) == "TRANSLATED"


def test_translate_fallback_labeled_when_unavailable(monkeypatch):
    # Force both Claude and offline MT unavailable -> labeled passthrough.
    monkeypatch.setattr(pp, "_claude", lambda *a, **k: None)
    import murti.translate_offline as to
    monkeypatch.setattr(to, "translate", lambda *a, **k: None)
    s = Settings(translate_enabled=True, target_language="French")
    out = pp.process("नमस्ते", "hi", s)
    assert out.startswith("[translate→French unavailable offline]")
