#!/usr/bin/env python3
"""Generate the visual hero demo (black & white, Apple-style).

Left: the app you *see* (a monochrome dictation window — mic, "Recording…",
waveform). A scan beam sweeps across. Right: what's *inside* — the core
pipeline plus the full feature set, revealed piece by piece. Captions narrate.

Self-contained CSS keyframes, no external tools. Renders inline on GitHub.
Regenerate with:  python3 demo/make_hero_svg.py
"""
from pathlib import Path

# ---- Murti palette (warm editorial dark + bronze accent) ------------------- #
BG, CARD, CARD2 = "#0e0d0c", "#161413", "#1d1a18"
FG, DIM, DIM2 = "#efe9e0", "#a69d8f", "#746b5f"
LINE = "#2a2622"
WHITE = "#c08a5a"   # bronze accent (reused wherever the mark needs emphasis)
W, H, CYCLE = 940, 600, 12.0
FONT = "'Helvetica Neue',-apple-system,BlinkMacSystemFont,system-ui,sans-serif"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def reveal_kf(name, t, fade=0.4, out=True):
    pi, pv = t / CYCLE * 100, (t + fade) / CYCLE * 100
    tail = "94%{opacity:1}100%{opacity:0}" if out else "100%{opacity:1}"
    return f"@keyframes {name}{{0%,{pi:.2f}%{{opacity:0}}{pv:.2f}%,{tail}}}"


def pulse_caption(name, t0, t1):
    a, b, c, d = (t0 / CYCLE * 100, (t0 + .3) / CYCLE * 100,
                  (t1 - .3) / CYCLE * 100, t1 / CYCLE * 100)
    return (f"@keyframes {name}{{0%,{a:.2f}%{{opacity:0}}{b:.2f}%,{c:.2f}%"
            f"{{opacity:1}}{d:.2f}%,100%{{opacity:0}}}}")


def box(x, y, w, h, title, sub, cls, strong=False):
    stroke = WHITE if strong else LINE
    tcol = WHITE if strong else FG
    t = (f'<g class="{cls}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" '
         f'fill="{CARD}" stroke="{stroke}" stroke-width="{1.6 if strong else 1}"/>'
         f'<text x="{x+16}" y="{y+(h/2 if not sub else h*0.40)}" fill="{tcol}" '
         f'font-size="14.5" font-weight="600">{esc(title)}</text>')
    if sub:
        t += (f'<text x="{x+16}" y="{y+h*0.73}" fill="{DIM}" font-size="11.5">'
              f'{esc(sub)}</text>')
    return t + "</g>"


def chip(x, y, w, label, cls):
    return (f'<g class="{cls}"><rect x="{x}" y="{y}" width="{w}" height="34" rx="8" '
            f'fill="{CARD2}" stroke="{LINE}"/>'
            f'<circle cx="{x+16}" cy="{y+17}" r="3" fill="{FG}"/>'
            f'<text x="{x+28}" y="{y+17}" fill="{FG}" font-size="12.5" '
            f'font-weight="500">{esc(label)}</text></g>')


def build():
    P = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="{FONT}">']

    chips = ["Meeting notetaker · Zoom", "Cloud sync", "Accounts & team",
             "Billing", "Voice profile", "Headset ring support",
             "Pause media", "Auto-learn dictionary"]
    css = [
        "text{dominant-baseline:middle}",
        reveal_kf("win", 0.2, out=False), reveal_kf("beam", 2.6),
        reveal_kf("head", 3.4, out=False),
        reveal_kf("p1", 3.9, out=False), reveal_kf("p2", 4.3, out=False),
        reveal_kf("p3", 4.7, out=False), reveal_kf("flag", 5.1, out=False),
        reveal_kf("fh", 5.4, out=False),
        *[reveal_kf(f"c{i}", 5.7 + i * 0.22, out=False) for i in range(len(chips))],
        ".win{opacity:1;animation:win %ss infinite}" % CYCLE,
        ".head{opacity:1;animation:head %ss infinite}" % CYCLE,
        ".flag{opacity:1;animation:flag %ss infinite}" % CYCLE,
        ".fh{opacity:1;animation:fh %ss infinite}" % CYCLE,
        *[f".p{i}{{opacity:1;animation:p{i} {CYCLE}s infinite}}" for i in (1, 2, 3)],
        *[f".c{i}{{opacity:1;animation:c{i} {CYCLE}s infinite}}" for i in range(len(chips))],
        ".beam{opacity:0;animation:beam %ss infinite,sweep %ss infinite}" % (CYCLE, CYCLE),
        "@keyframes sweep{0%,20%{transform:translateX(0)}32%{transform:translateX(430px)}"
        "40%,100%{transform:translateX(430px)}}",
        ".ring{transform-box:fill-box;transform-origin:center;animation:sonar 2s ease-out infinite}",
        "@keyframes sonar{0%{transform:scale(.6);opacity:.5}100%{transform:scale(1.6);opacity:0}}",
        ".bar{transform-box:fill-box;transform-origin:bottom;animation:wave 1.1s ease-in-out infinite}",
        "@keyframes wave{0%,100%{transform:scaleY(.25)}50%{transform:scaleY(1)}}",
        pulse_caption("q1", 0.4, 3.0), pulse_caption("q2", 3.2, 5.2),
        pulse_caption("q3", 5.4, 11.6),
        ".q1{opacity:0;animation:q1 %ss infinite}" % CYCLE,
        ".q2{opacity:0;animation:q2 %ss infinite}" % CYCLE,
        ".q3{opacity:0;animation:q3 %ss infinite}" % CYCLE,
    ]
    P.append("<style>" + "".join(css) + "</style>")

    P.append(f'<rect width="{W}" height="{H}" rx="14" fill="{BG}"/>')
    P.append(f'<text x="{W/2}" y="34" fill="{FG}" font-size="19" font-weight="700" '
             f'text-anchor="middle" letter-spacing="-0.5">Murti — see inside any app</text>')

    # ============ LEFT: the app you see (monochrome window) ============
    wx, wy, ww, wh = 40, 70, 380, 414
    P.append('<g class="win">')
    P.append(f'<rect x="{wx}" y="{wy}" width="{ww}" height="{wh}" rx="14" fill="{CARD}" '
             f'stroke="{LINE}"/>')
    P.append(f'<rect x="{wx}" y="{wy}" width="{ww}" height="36" rx="14" fill="{CARD2}"/>')
    P.append(f'<rect x="{wx}" y="{wy+24}" width="{ww}" height="12" fill="{CARD2}"/>')
    for i in range(3):
        P.append(f'<circle cx="{wx+22+i*18}" cy="{wy+18}" r="5" fill="none" '
                 f'stroke="{DIM2}" stroke-width="1.3"/>')
    P.append(f'<text x="{wx+ww/2}" y="{wy+18}" fill="{DIM}" font-size="12.5" '
             f'font-weight="600" text-anchor="middle">Example.app</text>')
    cx, cy = wx + ww / 2, wy + 148
    for d in (0, .6, 1.2):
        P.append(f'<circle class="ring" style="animation-delay:{d}s" cx="{cx}" cy="{cy}" '
                 f'r="44" fill="none" stroke="{WHITE}" stroke-width="1.5"/>')
    P.append(f'<circle cx="{cx}" cy="{cy}" r="44" fill="{WHITE}"/>')
    P.append(f'<path d="M{cx} {cy-16} a7 7 0 0 1 7 7 v6 a7 7 0 0 1-14 0 v-6 a7 7 0 0 1 7-7z" '
             f'fill="none" stroke="{BG}" stroke-width="2"/>')
    P.append(f'<path d="M{cx-11} {cy+1} a11 11 0 0 0 22 0 M{cx} {cy+12} v6" '
             f'fill="none" stroke="{BG}" stroke-width="2"/>')
    P.append(f'<text x="{cx}" y="{cy+74}" fill="{FG}" font-size="15" font-weight="600" '
             f'text-anchor="middle">Recording…</text>')
    bx, bbot, bw, gap, n = wx + 46, wy + 330, 8, 18, 16
    for i in range(n):
        P.append(f'<rect class="bar" style="animation-delay:{(i%6)*0.12:.2f}s" '
                 f'x="{bx+i*gap}" y="{bbot-58}" width="{bw}" height="58" rx="3" '
                 f'fill="{FG if i%2 else DIM}"/>')
    P.append(f'<text x="{cx}" y="{wy+wh-24}" fill="{DIM2}" font-size="12" '
             f'text-anchor="middle">what the user sees</text>')
    P.append('</g>')

    # scan beam
    P.append(f'<g class="beam"><rect x="{wx+ww/2-2}" y="60" width="4" height="434" rx="2" '
             f'fill="{WHITE}" opacity="0.9"/>'
             f'<rect x="{wx+ww/2-12}" y="60" width="24" height="434" fill="{WHITE}" '
             f'opacity="0.12"/></g>')

    # ============ RIGHT: what's inside ============
    rx0 = 480
    P.append(f'<text class="head" x="{rx0}" y="80" fill="{FG}" font-size="13" '
             f'font-weight="700" letter-spacing="1">WHAT’S ACTUALLY INSIDE</text>')
    bw2 = 420
    P.append(box(rx0, 94, bw2, 44, "Microphone  →  Opus encoder", "AudioWorklet · WASM workers", "p1"))
    P.append(f'<text class="p2" x="{rx0+bw2/2}" y="150" fill="{DIM2}" font-size="15" text-anchor="middle">↓</text>')
    P.append(box(rx0, 160, bw2, 44, "gRPC stream", "@grpc/grpc-js", "p2"))
    P.append(f'<text class="p3" x="{rx0+bw2/2}" y="216" fill="{DIM2}" font-size="15" text-anchor="middle">↓</text>')
    P.append(box(rx0, 226, bw2, 46, "Cloud transcription", "not on your device", "p3", strong=True))
    P.append(f'<text class="flag" x="{rx0}" y="292" fill="{DIM}" font-size="12">'
             f'⚑ no on-device speech model found in the binary</text>')

    P.append(f'<text class="fh" x="{rx0}" y="322" fill="{FG}" font-size="13" '
             f'font-weight="700" letter-spacing="1">FEATURES FOUND</text>')
    cw = 204
    for i, label in enumerate(chips):
        col, rowi = i % 2, i // 2
        cxx = rx0 + col * (cw + 12)
        cyy = 334 + rowi * 42
        P.append(chip(cxx, cyy, cw, label, f"c{i}"))

    # captions
    cy2 = H - 34
    for cls, txt in (("q1", "This is the app you use."),
                     ("q2", "Teardown x-rays the shipped binary…"),
                     ("q3", "…and reveals everything inside. No source code.")):
        P.append(f'<text class="{cls}" x="{W/2}" y="{cy2}" fill="{FG}" font-size="15.5" '
                 f'font-weight="600" text-anchor="middle">{esc(txt)}</text>')

    P.append("</svg>")
    return "\n".join(P)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "murti-hero.svg"
    out.write_text(build())
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)")
