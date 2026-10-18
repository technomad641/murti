"""Pause media + duck other audio while dictating (local, macOS).

Uses `osascript` / `afplay`-free system controls. The command runner is
injectable so the logic is unit-testable without touching the system.
"""
from __future__ import annotations

import shutil
import subprocess

# Players we try to pause. AppleScript "is running" guards avoid launching them.
_PAUSE = [
    'tell application "System Events" to if (exists process "Music") then '
    'tell application "Music" to if player state is playing then pause',
    'tell application "System Events" to if (exists process "Spotify") then '
    'tell application "Spotify" to if player state is playing then pause',
]
_PLAY = [
    'tell application "System Events" to if (exists process "Music") then '
    'tell application "Music" to if player state is paused then play',
    'tell application "System Events" to if (exists process "Spotify") then '
    'tell application "Spotify" to if player state is paused then play',
]


def _default_runner(script: str) -> str:
    if not shutil.which("osascript"):
        return ""
    try:
        return subprocess.run(["osascript", "-e", script],
                              capture_output=True, text=True, timeout=4).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


class MediaController:
    """Pause/resume players and duck system output volume while dictating."""

    def __init__(self, runner=_default_runner):
        self._run = runner
        self._saved_volume: int | None = None
        self._paused = False

    # ------------------------------------------------------------- pause
    def pause_media(self) -> None:
        for s in _PAUSE:
            self._run(s)
        self._paused = True

    def resume_media(self) -> None:
        if not self._paused:
            return
        for s in _PLAY:
            self._run(s)
        self._paused = False

    # ------------------------------------------------------------- duck
    def duck_audio(self) -> None:
        """Remember current output volume and mute it (so audio won't bleed in)."""
        if self._saved_volume is not None:
            return
        cur = self._run("output volume of (get volume settings)")
        try:
            self._saved_volume = int(cur)
        except (TypeError, ValueError):
            self._saved_volume = None
            return
        self._run("set volume output volume 0")

    def restore_audio(self) -> None:
        if self._saved_volume is None:
            return
        self._run(f"set volume output volume {self._saved_volume}")
        self._saved_volume = None

    # ------------------------------------------------------------- combo
    def on_record_start(self, pause: bool, mute: bool) -> None:
        if pause:
            self.pause_media()
        if mute:
            self.duck_audio()

    def on_record_stop(self, pause: bool, mute: bool) -> None:
        if mute:
            self.restore_audio()
        if pause:
            self.resume_media()
