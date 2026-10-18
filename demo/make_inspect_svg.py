#!/usr/bin/env python3
"""Generate an animated SVG terminal demo of Teardown (no external tools).

Produces `demo/murti-inspect.svg`: a looping, self-contained terminal cast that
reveals one line at a time via CSS keyframes. Renders inline on GitHub.

Regenerate with:  python3 demo/make_demo_svg.py
"""
from pathlib import Path

# ---- Murti palette (warm editorial dark + bronze accent) ------------------- #
BG, BAR, FG = "#0e0d0c", "#1d1a18", "#efe9e0"
# "Accent" roles collapse to bronze; the rest to warm grays.
GREEN, CYAN, BLUE = "#c08a5a", "#c08a5a", "#a69d8f"
DIM, YELLOW, PATH = "#746b5f", "#c08a5a", "#a69d8f"
RED_DOT = YEL_DOT = GRN_DOT = "none"  # hollow traffic lights (outlined below)

# ---- script: (reveal_seconds, text, color) -------------------------------- #
# ⁣ keeps leading spaces (indent) from being collapsed.
LINES = [
    (0.3, "$ murti inspect \"/Applications/Wispr Flow.app\"", GREEN),
    (1.1, "  • target: app.asar   (electron bundle, 134 MB)", DIM),
    (1.7, "  • running REA:  rea inspect-artifact …", DIM),
    (2.5, "  ✓ 999 files mapped from the raw binary — no source", BLUE),
    (3.2, "", FG),
    (3.4, "  # Architecture X-ray — Wispr Flow", CYAN),
    (3.8, "    Electron · webpack · v1.6.1147", DIM),
    (4.2, "    ├─ node_sqlite3.node        → local database", FG),
    (4.5, "    ├─ opusscript_native.wasm   → Opus audio codec", FG),
    (4.8, "    ├─ panel_activation.node    → global hotkey", FG),
    (5.1, "    ├─ recorderWorklet.js       → microphone capture", FG),
    (5.4, "    ├─ accessibility_drop/      → AX text insertion", FG),
    (5.7, "    └─ @grpc/grpc-js            → cloud backend", FG),
    (6.3, "    ⚑ no on-device model  →  transcription is cloud", YELLOW),
    (6.9, "    9 renderer windows · 3 integrity flags", DIM),
    (7.3, "    → next probe: analyze-javascript-application", BLUE),
    (8.0, "", FG),
    (8.2, "  one command. zero source code. full blueprint.", GREEN),
]

CYCLE = 11.0          # seconds per loop
FADE = 0.35           # fade-in duration
PAD_X, TOP = 26, 78   # text left pad, first line y
LH = 25               # line height
W, H = 900, TOP + LH * len(LINES) + 26
FONT = ("'SF Mono','DejaVu Sans Mono',Menlo,Consolas,monospace")


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def keyframes() -> str:
    """One keyframe set per line: fade in at its moment, hold, fade at loop end."""
    out = []
    for i, (t, _txt, _c) in enumerate(LINES):
        p_in = max(0.0, t / CYCLE * 100)
        p_vis = min(99.0, (t + FADE) / CYCLE * 100)
        # base opacity:1 → if a renderer ignores CSS animation, all text still
        # shows (graceful fallback); where animation runs, keyframes reveal it.
        out.append(
            f".l{i}{{opacity:1;animation:k{i} {CYCLE}s infinite;}}"
            f"@keyframes k{i}{{0%,{p_in:.2f}%{{opacity:0}}"
            f"{p_vis:.2f}%,94%{{opacity:1}}100%{{opacity:0}}}}")
    return "".join(out)


def build() -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{FONT}" font-size="15">',
        "<style>",
        f"text{{dominant-baseline:middle}}"
        f".cur{{animation:blink 1s steps(1) infinite}}"
        f"@keyframes blink{{0%,50%{{opacity:1}}50.01%,100%{{opacity:0}}}}",
        keyframes(),
        "</style>",
        # window
        f'<rect width="{W}" height="{H}" rx="12" fill="{BG}"/>',
        f'<rect width="{W}" height="40" rx="12" fill="{BAR}"/>',
        f'<rect y="28" width="{W}" height="12" fill="{BAR}"/>',
        f'<circle cx="24" cy="20" r="5.5" fill="none" stroke="{DIM}" stroke-width="1.3"/>',
        f'<circle cx="43" cy="20" r="5.5" fill="none" stroke="{DIM}" stroke-width="1.3"/>',
        f'<circle cx="62" cy="20" r="5.5" fill="none" stroke="{DIM}" stroke-width="1.3"/>',
        f'<text x="{W/2}" y="20" fill="{DIM}" font-size="13" '
        f'text-anchor="middle">murti — zsh</text>',
    ]
    for i, (_t, txt, color) in enumerate(LINES):
        y = TOP + i * LH
        content = esc(txt) if txt else " "
        parts.append(
            f'<text class="l{i}" x="{PAD_X}" y="{y}" fill="{color}" '
            f'xml:space="preserve">{content}</text>')
    # blinking cursor on the last visible line
    last_y = TOP + (len(LINES) - 1) * LH
    cur_x = PAD_X + 8 + len(LINES[-1][1]) * 9
    parts.append(
        f'<rect class="cur l{len(LINES)-1}" x="{cur_x}" y="{last_y-9}" '
        f'width="9" height="18" fill="{GREEN}"/>')
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "murti-inspect.svg"
    out.write_text(build())
    print(f"wrote {out}  ({out.stat().st_size:,} bytes, {len(LINES)} lines)")
