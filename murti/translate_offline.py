"""Offline neural translation via argos-translate (English <-> Hindi).

Best-effort and optional: used only when the online Claude path is unavailable.
Only en/hi are supported offline (the installed argos packages); other target
languages return None so the caller can fall back to a labeled placeholder.
"""
from __future__ import annotations

_LANG_CODES = {"english": "en", "hindi": "hi", "en": "en", "hi": "hi"}


def _code(name: str | None) -> str | None:
    if not name:
        return None
    return _LANG_CODES.get(name.strip().lower())


def available() -> bool:
    try:
        import argostranslate.translate as tr

        codes = {lang.code for lang in tr.get_installed_languages()}
        return {"en", "hi"} <= codes
    except Exception:
        return False


def translate(text: str, source_lang: str | None, target_language: str) -> str | None:
    """Translate text to target_language. Returns None if not possible offline."""
    try:
        import argostranslate.translate as tr
    except Exception:
        return None

    tgt = _code(target_language)
    if tgt is None:
        return None  # offline supports only en/hi targets

    src = _code(source_lang)
    if src is None:
        # Whisper lang code may be e.g. "hi"/"en"; otherwise guess by script.
        from .postprocess import has_devanagari

        src = "hi" if has_devanagari(text) else "en"
    if src == tgt:
        return text
    try:
        out = tr.translate(text, src, tgt)
        return out or None
    except Exception:
        return None
