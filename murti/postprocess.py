"""Shape the raw transcript into the user's desired output.

Hybrid by design (see Settings):
  * transcribe mode + romanized  -> Claude romanizes Devanagari to natural
      Hinglish when online; otherwise an offline rule-based transliteration.
  * transcribe mode + devanagari -> raw text, optionally tidied by Claude.
  * translate mode               -> Claude translates to the target language
      (requires network + API key; falls back to returning the raw text).
"""
from __future__ import annotations

import os
import re

from .config import Settings

# Devanagari Unicode block.
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI.search(text))


# --------------------------------------------------------------------------- #
# Offline romanization (best-effort, no network)                              #
# --------------------------------------------------------------------------- #
def romanize_offline(text: str) -> str:
    """Transliterate Devanagari spans to readable ASCII Latin; pass English through.

    Uses indic_transliteration (ITRANS), then lowercases. This is approximate
    Hinglish — the online path produces much more natural spelling.
    """
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
    except Exception:
        return text

    def _tx(match: re.Match) -> str:
        span = match.group(0)
        # Normalize rare candra vowels ITRANS handles poorly.
        span = span.replace("ऑ", "ओ").replace("ऍ", "ए").replace("ॉ", "ो")
        out = transliterate(span, sanscript.DEVANAGARI, sanscript.ITRANS)
        # Schwa deletion: Hindi drops the inherent short 'a' at word ends
        # (e.g. नाम = "nAma" -> "naam"). Do this BEFORE lowercasing so the long
        # vowel 'A' is preserved and only the short schwa 'a' is removed.
        out = re.sub(r"(?<=[a-zA-Z])a\b", "", out)
        # ITRANS markers / long-vowel caps -> casual Hinglish lowercase.
        out = out.replace(".c", "").replace("~", "").replace("^", "")
        out = re.sub(r"\.(?=[A-Za-z])", "", out)  # drop nukta dots (ड़ -> "D")
        # Anusvara (ं) comes out of ITRANS as "M". The nasal reads as "m" before
        # a labial (p/b/m) and "n" elsewhere: मीटिंग -> "meeting", अटेंड -> "atend".
        out = re.sub(r"M(?=[pbmPBM])", "m", out)
        out = out.replace("M", "n")
        out = out.replace("A", "aa").replace("I", "ee").replace("U", "oo")
        return out.lower()

    # Transliterate maximal runs of Devanagari (plus combining marks).
    return re.sub(r"[ऀ-ॿ]+", _tx, text)


# --------------------------------------------------------------------------- #
# Online assist via Claude                                                    #
# --------------------------------------------------------------------------- #
def _claude_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _build_system(settings: Settings, mode: str) -> str:
    base = (
        "You are a post-processor for a dictation app. You receive raw "
        "speech-to-text output and return cleaned text. Output ONLY the final "
        "text — no quotes, no explanation, no preamble."
    )
    if mode == "translate":
        romanize = (
            " If the target language is Hindi, output natural romanized Hinglish "
            "in Latin script (not Devanagari)."
            if settings.hindi_script == "romanized"
            else ""
        )
        return (
            base
            + f" Translate the input into {settings.target_language}, preserving "
            "meaning and tone." + romanize
        )
    if mode == "romanize":
        return (
            base
            + " Rewrite the input so that any Hindi/Devanagari becomes natural "
            "romanized Hinglish as an Indian bilingual would type it in Latin "
            "script (e.g. 'मुझे कल office जाना है' -> 'mujhe kal office jaana hai'). "
            "Render English words and loanwords in standard English spelling "
            "(office, meeting, project, update). Keep all words and meaning; only "
            "fix script, spelling, capitalization and punctuation."
        )
    # cleanup (keep Devanagari, just tidy)
    return (
        base
        + " Keep the original scripts (Devanagari stays Devanagari, English stays "
        "English). Only fix capitalization, spacing and punctuation. Do not "
        "translate or transliterate."
    )


def _claude(raw: str, settings: Settings, mode: str) -> str | None:
    """Return Claude's processed text, or None if unavailable/failed."""
    if not _claude_available():
        return None
    try:
        from anthropic import Anthropic

        client = Anthropic()
        msg = client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            system=_build_system(settings, mode),
            messages=[{"role": "user", "content": raw}],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        out = "".join(parts).strip()
        return out or None
    except Exception:
        return None  # network down, bad key, etc. -> caller falls back


def _romanize_if_hindi_target(text: str, settings: Settings) -> str:
    """After translating to Hindi, romanize to Hinglish if that's the chosen script."""
    if (
        settings.target_language.strip().lower() == "hindi"
        and settings.hindi_script == "romanized"
        and has_devanagari(text)
    ):
        return romanize_offline(text)
    return text


# --------------------------------------------------------------------------- #
# Orchestrator                                                                #
# --------------------------------------------------------------------------- #
def process(raw: str, detected_lang: str | None, settings: Settings) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""

    if settings.translate_enabled:
        # 1) best quality: Claude (online)
        out = _claude(raw, settings, mode="translate")
        if out is not None:
            return _romanize_if_hindi_target(out, settings)
        # 2) offline neural MT (en<->hi only)
        from . import translate_offline

        out = translate_offline.translate(raw, detected_lang, settings.target_language)
        if out is not None:
            return _romanize_if_hindi_target(out, settings)
        # 3) nothing available -> labeled passthrough (honest "dummy")
        return f"[translate→{settings.target_language} unavailable offline] {raw}"

    # transcribe (in-language) mode
    if settings.hindi_script == "devanagari":
        if settings.online_cleanup:
            out = _claude(raw, settings, mode="cleanup")
            if out:
                return out
        return raw

    # romanized Hinglish output
    if not has_devanagari(raw):
        # pure English (or already Latin) -> optional light cleanup
        if settings.online_cleanup:
            out = _claude(raw, settings, mode="cleanup")
            if out:
                return out
        return raw
    if settings.online_cleanup:
        out = _claude(raw, settings, mode="romanize")
        if out:
            return out
    return romanize_offline(raw)
