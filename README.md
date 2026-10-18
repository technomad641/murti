<div align="center">

# Murti · मूर्ति

### Voice, given form.

**Speak anywhere on your Mac. Murti carves your raw voice into finished text —
English, Hindi, and Hinglish — entirely on your device.**
Plus a studio tool that reads any app you own and reveals the form hidden inside it.

<img src="demo/murti-hero.svg" alt="Murti — an app being x-rayed into its architecture" width="100%">

<sub>Local Whisper on the Apple Silicon GPU · nothing leaves your machine · built with Claude Code</sub>

</div>

---

## The idea

A *murti* is raw stone given form by a sculptor. **Murti** does the same to your
voice: you speak, and it chisels the messy, half-formed sound into clean, punctuated
text and drops it wherever your cursor is — a message, a doc, an email, your IDE.

No accounts. No upload. The transcription runs **on your device**.

<div align="center">
<img src="demo/dashboard.png" alt="The Murti dashboard" width="88%">
</div>

## What it does

| | |
|---|---|
| 🎙️ **Dictate anywhere** | Press **⌘⌥D**, speak, press again. It transcribes and types at your cursor in any app. |
| 🌐 **English · Hindi · Hinglish** | True code-switching. Hindi comes out **romanized (Hinglish)** by default, or Devanagari — your choice. |
| 🧠 **On-device** | Whisper `large-v3-turbo` runs locally on the Apple Silicon GPU. Private and offline. |
| ⏸️ **Pause media while you speak** | Music / Spotify / video auto-pause when you start and resume after. |
| 🔇 **Mute other audio** | Ducks system output so nothing bleeds into your mic. |
| 📖 **Auto-learning dictionary** | Learns the names and jargon you dictate so it spells them right next time. |
| 📈 **Insights & voice profile** | Words dictated, words-per-minute, time saved, streaks — computed locally. |
| 🎧 **Headset & ring support** | Detects headsets and call-control rings, prefers them automatically. |
| 🔎 **Inspect** *(studio)* | Point Murti at any app you own and get its full architecture from the shipped binary. No source code. |
| ☁️ **Cloud, optional** | Meeting notetaker (Zoom), accounts, team, billing and sync are available on top — the dictation core never needs them. |

## How it works

```
 ⌘⌥D  →  record mic (16 kHz)  →  Whisper large-v3-turbo (local, MLX GPU)
                                          │
                                   shape the text
                      ├─ romanize Hindi  (rules offline · Claude online)
                      ├─ translate       (argos offline · Claude online)
                      └─ personal dictionary + corrections
                                          │
                           paste at your cursor (⌘V)
```

Everything in that path is **local by default**. The optional online step (Claude)
only polishes romanization/translation when you have a key — and transcription is
*always* on-device regardless.

The **dashboard** above is served by a tiny `127.0.0.1`-only server
(`murti/dashboard.py`) wired straight to the live engine: the toggles, insights and
your dictionary are the real on-device state, read and written in place.

## Install & run

Requires **macOS (Apple Silicon)**, **Python 3.12**, and [`uv`](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/technomad641/murti.git
cd murti
uv venv --python 3.12 .venv
uv pip install -r requirements.txt

./run.sh          # launches the menu-bar app + dashboard
```

A 🎙️ appears in your menu bar. Open **Dashboard** from its menu, then press
**⌘⌥D** anywhere to dictate.

### Permissions (first run)

macOS will prompt — grant all three in **System Settings → Privacy & Security**:
**Microphone** (record) · **Accessibility** (paste) · **Input Monitoring** (hotkey).

### Configure without editing JSON

```sh
./.venv/bin/python -m murti.configure --translate on --target Hindi
./.venv/bin/python -m murti.configure --script devanagari
```

### The Inspect tool

```sh
./.venv/bin/python -m murti.inspect "/Applications/Some App.app"
```

Reads the shipped binary and prints an architecture report (frameworks, native
modules, windows, backend). Structural metadata only — **no source, assets, or
secrets, and nothing that bypasses licensing or DRM.** For apps you own or are
authorized to analyze. Powered by the [REA](https://www.npmjs.com/package/rea-agents)
reverse-engineering engine. (The hero above is a real Inspect run.)

## Tests

```sh
./.venv/bin/python -m pytest tests -q        # 34 offline tests, no mic / no network
```

## Privacy

- **Transcription is on-device.** Your voice is not uploaded for dictation.
- Settings, dictionary and insights live locally in `~/.config/murti/`.
- The dashboard server binds to `127.0.0.1` only.
- Cloud features (meetings, accounts, sync) are opt-in and clearly marked.

## Design

The interface follows an editorial, gallery-grade system — **Instrument Serif**
display type over **Hanken Grotesk**, a bone-paper canvas, a single cool slate
accent, and an 8-pt grid. Warm, calm, and unmistakably its own.

## License

MIT © Rajat Singh — see [LICENSE](LICENSE).

<div align="center"><sub><i>मूर्ति — form, given to the formless.</i></sub></div>
