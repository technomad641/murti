"""User settings, persisted as JSON under ~/.config/murti/config.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "murti"
CONFIG_PATH = CONFIG_DIR / "config.json"
_LEGACY_DIR = Path.home() / ".config" / "dictation"  # pre-"Vox" rename


def _migrate_legacy() -> None:
    """One-time: carry settings/dictionary/insights over from the old name."""
    try:
        if _LEGACY_DIR.exists() and not CONFIG_DIR.exists():
            import shutil
            shutil.copytree(_LEGACY_DIR, CONFIG_DIR)
    except Exception:  # noqa: BLE001 — migration is best-effort
        pass


_migrate_legacy()


@dataclass
class Settings:
    # --- speech-to-text ---
    engine: str = "mlx"                  # "mlx" (GPU) or "faster-whisper" (CPU fallback)
    model_name: str = "large-v3-turbo"  # faster-whisper model name

    # --- output shaping ---
    translate_enabled: bool = False      # toggle: translate result vs transcribe in-language
    target_language: str = "English"     # used only when translate_enabled
    hindi_script: str = "romanized"       # "romanized" (Hinglish) or "devanagari"

    # --- online assist (Claude) ---
    # Used for high-quality romanization/cleanup and for translation. Falls back
    # to offline transliteration when no API key or no network.
    claude_model: str = "claude-haiku-5-5"  # fast + cheap; good for short post-edits
    online_cleanup: bool = True             # use Claude to tidy transcribe-mode text when available

    # --- input ---
    hotkey: str = "<cmd>+<alt>+d"  # pynput GlobalHotKeys spec; push-to-toggle recording
    input_device: str = ""         # preferred mic name; "" = system default

    # --- latency ---
    streaming: bool = True          # transcribe while you speak (instant stop)
    warm_on_launch: bool = True     # preload the model at startup (no cold start)

    # --- while-dictating behavior (local, on-device) ---
    pause_media: bool = True        # pause Music/Spotify/video while recording
    mute_others: bool = False       # duck system output volume while recording
    prefer_headset: bool = True     # switch to a connected headset automatically

    # --- personalization (local) ---
    auto_learn: bool = True         # auto-add dictated names/jargon to the dictionary

    # --- cloud features (stubbed UI; require an account) ---
    cloud_sync: bool = False

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))

    @classmethod
    def load(cls) -> "Settings":
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text())
                known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
                return cls(**known)
            except Exception:
                pass  # corrupt/old config -> fall back to defaults
        return cls()
