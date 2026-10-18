"""Permission-free demo of the full dictation pipeline.

Transcribes each sample clip once (local Whisper), then shows how the raw text
is shaped under three modes: romanized Hinglish, Devanagari, and translate->English.
Writes a console summary and an HTML report with playable audio.

Run:  ./.venv/bin/python scripts/demo.py
"""
from __future__ import annotations

import html
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from murti import postprocess  # noqa: E402
from murti.audio_io import load_wav_16k_mono  # noqa: E402
from murti.config import Settings  # noqa: E402
from murti.stt import make_engine  # noqa: E402

AUD = ROOT / "tests" / "audio"
OUT = ROOT / "demo"

# (file stem, human label)
CLIPS = [
    ("en", "English"),
    ("en2", "English (longer)"),
    ("hi", "Hindi"),
    ("hi2", "Hindi (longer)"),
    ("hinglish", "Hinglish / code-switch"),
    ("mix2", "Hinglish / code-switch 2"),
]

BASE = Settings()
MODES = [
    ("Transcribe · Romanized (Hinglish)", replace(BASE, translate_enabled=False, hindi_script="romanized")),
    ("Transcribe · Devanagari", replace(BASE, translate_enabled=False, hindi_script="devanagari", online_cleanup=False)),
    ("Translate → English", replace(BASE, translate_enabled=True, target_language="English")),
]


def main(argv=None) -> int:
    OUT.mkdir(exist_ok=True)
    clips = [(stem, label) for stem, label in CLIPS if (AUD / f"{stem}.wav").exists()]
    cache = OUT / "transcripts.json"
    html_only = "--html-only" in (argv or sys.argv[1:])

    transcripts: dict[str, tuple[str, str]] = {}
    if html_only:
        # Rebuild the report from cached transcripts (fast, no model needed).
        import json

        if not cache.exists():
            print("no cached transcripts; run without --html-only first")
            return 2
        raw_cache = json.loads(cache.read_text(encoding="utf-8"))
        transcripts = {k: (v[0], v[1]) for k, v in raw_cache.items()}
        print(f"Rebuilding report from {cache} ({len(transcripts)} clips)")
    else:
        import json

        print("Loading STT engine (local)...")
        engine = make_engine(BASE.engine, BASE.model_name)
        for stem, label in clips:
            audio = load_wav_16k_mono(str(AUD / f"{stem}.wav"))
            t0 = time.time()
            raw, lang = engine.transcribe(audio)
            transcripts[stem] = (raw, lang or "?")
            print(f"  [{stem:9s}] {time.time()-t0:4.1f}s  lang={lang}  {raw[:60]}")
        cache.write_text(json.dumps(transcripts, ensure_ascii=False, indent=2), encoding="utf-8")

    clips = [(s, lbl) for s, lbl in clips if s in transcripts]

    key = "set" if postprocess._claude_available() else "NOT set"
    off = "available" if __import__("murti.translate_offline", fromlist=["available"]).available() else "unavailable"
    print(f"\nANTHROPIC_API_KEY: {key}   |   offline MT: {off}\n")

    rows = []
    for stem, label in clips:
        raw, lang = transcripts[stem]
        print(f"\n===== {label}  (lang={lang}) =====")
        print(f"  raw: {raw}")
        mode_outputs = []
        for mode_label, settings in MODES:
            final = postprocess.process(raw, lang, settings)
            print(f"  [{mode_label}] -> {final}")
            mode_outputs.append((mode_label, final))
        rows.append((stem, label, lang, raw, mode_outputs))

    _write_html(rows, key, off)
    print(f"\nHTML report: {OUT / 'report.html'}")
    return 0


def _write_html(rows, key_status, off_status):
    esc = html.escape
    cards = []
    for stem, label, lang, raw, mode_outputs in rows:
        mode_html = "".join(
            f"<div class='mode'><div class='ml'>{esc(ml)}</div>"
            f"<div class='mv'>{esc(final)}</div></div>"
            for ml, final in mode_outputs
        )
        cards.append(f"""
        <section class="card">
          <header><h2>{esc(label)}</h2><span class="lang">detected: {esc(lang)}</span></header>
          <audio controls src="../tests/audio/{esc(stem)}.wav"></audio>
          <div class="raw"><span class="tag">raw transcript</span>{esc(raw)}</div>
          {mode_html}
        </section>""")

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dictation Demo</title>
<style>
  :root {{ --bg:#0f1115; --card:#191c23; --fg:#e8eaed; --mut:#9aa0aa; --acc:#6ea8fe; }}
  @media (prefers-color-scheme: light) {{ :root {{ --bg:#f5f6f8; --card:#fff; --fg:#1b1d22; --mut:#5a606b; --acc:#2962ff; }} }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:24px 16px 48px; background:var(--bg); color:var(--fg);
         font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  .wrap {{ max-width:860px; margin:0 auto; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  .sub {{ color:var(--mut); margin:0 0 20px; font-size:13px; }}
  .status {{ font-size:12px; color:var(--mut); margin-bottom:20px; }}
  .status b {{ color:var(--fg); }}
  .banner {{ background:rgba(255,196,0,.12); border:1px solid rgba(255,196,0,.4);
             color:var(--fg); border-radius:10px; padding:10px 14px; font-size:13px;
             line-height:1.45; margin:0 0 14px; }}
  .banner code {{ font-size:12px; background:rgba(128,128,128,.18); padding:1px 5px; border-radius:4px; }}
  .card {{ background:var(--card); border-radius:14px; padding:16px 18px; margin:14px 0;
           box-shadow:0 1px 3px rgba(0,0,0,.25); }}
  header {{ display:flex; align-items:baseline; justify-content:space-between; }}
  h2 {{ font-size:16px; margin:0 0 8px; }}
  .lang {{ color:var(--mut); font-size:12px; }}
  audio {{ width:100%; height:34px; margin:6px 0 12px; }}
  .raw {{ color:var(--mut); font-size:14px; margin-bottom:12px; word-break:break-word; }}
  .tag {{ display:inline-block; font-size:10px; text-transform:uppercase; letter-spacing:.06em;
          color:var(--acc); margin-right:8px; }}
  .mode {{ display:grid; grid-template-columns:200px 1fr; gap:10px; padding:8px 0;
           border-top:1px solid rgba(128,128,128,.15); }}
  .ml {{ color:var(--mut); font-size:13px; }}
  .mv {{ font-weight:500; word-break:break-word; }}
  @media (max-width:560px) {{ .mode {{ grid-template-columns:1fr; gap:2px; }} }}
</style></head>
<body><div class="wrap">
  <h1>🎙️ Dictation — pipeline demo</h1>
  <p class="sub">Local Whisper transcription → post-processing. English, Hindi, and code-switched Hinglish.</p>
  <div class="banner">⚠️ <b>These clips are synthesized</b> with macOS <code>say</code> voices for a hands-off demo,
     so a few words come out robotic (e.g. "team"→"Tim", "park"→"part"). Your real voice through the
     microphone will transcribe noticeably cleaner.</div>
  <p class="status">ANTHROPIC_API_KEY: <b>{esc(key_status)}</b> &nbsp;·&nbsp; offline translation: <b>{esc(off_status)}</b>
     &nbsp;·&nbsp; when the key is set, romanization & translation use Claude for higher quality.</p>
  {''.join(cards)}
</div></body></html>"""
    (OUT / "report.html").write_text(doc, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
