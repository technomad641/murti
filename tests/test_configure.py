"""Tests for the config CLI (uses a temp config path, no real writes)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import murti.config as config  # noqa: E402
from murti import configure  # noqa: E402
from murti.config import Settings  # noqa: E402


def _use_tmp_config(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", cfg)
    monkeypatch.setattr(configure, "CONFIG_PATH", cfg)
    return cfg


def test_set_translate_and_script(monkeypatch, tmp_path):
    cfg = _use_tmp_config(monkeypatch, tmp_path)
    configure.main(["--translate", "on", "--script", "devanagari"])
    s = Settings.load()
    assert s.translate_enabled is True
    assert s.hindi_script == "devanagari"
    assert cfg.exists()


def test_set_target_and_engine(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    configure.main(["--target", "Hindi", "--engine", "faster-whisper"])
    s = Settings.load()
    assert s.target_language == "Hindi"
    assert s.engine == "faster-whisper"


def test_no_args_does_not_write(monkeypatch, tmp_path):
    cfg = _use_tmp_config(monkeypatch, tmp_path)
    configure.main([])
    assert not cfg.exists()  # viewing only, no changes


def test_apply_reports_changes():
    s = Settings()
    args = configure.build_parser().parse_args(["--translate", "on"])
    changes = configure.apply(s, args)
    assert s.translate_enabled is True
    assert any("translate_enabled" in c for c in changes)
