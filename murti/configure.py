"""Tiny CLI to view and change settings without editing JSON by hand.

Examples:
  python -m murti.configure                      # show current settings
  python -m murti.configure --translate on
  python -m murti.configure --script devanagari
  python -m murti.configure --target Hindi
  python -m murti.configure --engine faster-whisper
  python -m murti.configure --hotkey "<cmd>+<alt>+d"
"""
from __future__ import annotations

import argparse
from dataclasses import asdict

from .config import CONFIG_PATH, Settings

_ON = {"on", "true", "1", "yes", "y"}
_OFF = {"off", "false", "0", "no", "n"}


def _bool(value: str) -> bool:
    v = value.strip().lower()
    if v in _ON:
        return True
    if v in _OFF:
        return False
    raise argparse.ArgumentTypeError(f"expected on/off, got {value!r}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="murti.configure", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--translate", type=_bool, metavar="on|off",
                   help="enable/disable translate mode")
    p.add_argument("--script", choices=["romanized", "devanagari"],
                   help="Hindi output script")
    p.add_argument("--target", metavar="LANGUAGE", help="translation target language")
    p.add_argument("--engine", choices=["mlx", "faster-whisper"], help="STT backend")
    p.add_argument("--online-cleanup", type=_bool, metavar="on|off",
                   help="use Claude to tidy output when a key is present")
    p.add_argument("--claude-model", metavar="MODEL", help="Claude model id")
    p.add_argument("--hotkey", metavar="SPEC", help='pynput hotkey, e.g. "<cmd>+<alt>+d"')
    return p


def apply(settings: Settings, args: argparse.Namespace) -> list[str]:
    """Mutate settings from parsed args; return human-readable change list."""
    changes: list[str] = []
    mapping = {
        "translate": "translate_enabled",
        "script": "hindi_script",
        "target": "target_language",
        "engine": "engine",
        "online_cleanup": "online_cleanup",
        "claude_model": "claude_model",
        "hotkey": "hotkey",
    }
    for arg_name, field in mapping.items():
        val = getattr(args, arg_name)
        if val is not None:
            old = getattr(settings, field)
            if old != val:
                setattr(settings, field, val)
                changes.append(f"{field}: {old!r} -> {val!r}")
    return changes


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.load()
    changes = apply(settings, args)
    if changes:
        settings.save()
        print("Updated " + str(CONFIG_PATH) + ":")
        for c in changes:
            print("  " + c)
    else:
        print("Current settings (" + str(CONFIG_PATH) + "):")
        for k, v in asdict(settings).items():
            print(f"  {k:18s} {v!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
