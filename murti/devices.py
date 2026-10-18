"""Audio input devices + headset detection (local).

Wraps sounddevice when available; degrades gracefully when it isn't.
"""
from __future__ import annotations

import re

_HEADSET_HINTS = re.compile(
    r"airpods|jabra|bose|sony|headset|headphone|buds|wh-|wf-|earbud|plantronics|poly",
    re.IGNORECASE)


def list_input_devices() -> list[dict]:
    """Return [{index, name, channels, default, headset}] for input devices."""
    try:
        import sounddevice as sd
    except Exception:  # noqa: BLE001 — sounddevice/portaudio not available
        return []
    try:
        default_in = sd.default.device[0]
        devices = sd.query_devices()
    except Exception:  # noqa: BLE001
        return []
    out = []
    for i, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0:
            name = d.get("name", f"Device {i}")
            out.append({
                "index": i,
                "name": name,
                "channels": d["max_input_channels"],
                "default": i == default_in,
                "headset": bool(_HEADSET_HINTS.search(name)),
            })
    return out


def is_headset(name: str) -> bool:
    return bool(_HEADSET_HINTS.search(name or ""))


def detect_headset(devices: list[dict] | None = None) -> dict | None:
    """Return the first connected headset-like input device, if any."""
    for d in (devices if devices is not None else list_input_devices()):
        if d.get("headset"):
            return d
    return None
