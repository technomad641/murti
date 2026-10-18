# 📣 Murti — Share Kit

Everything you need to make Murti go viral. **Nothing here is posted
automatically** — these are drafts for *you* to record and publish.

The inline README demo (`teardown-demo.svg`) is already a looping "video." Use
the storyboard below if you want a real screen-recorded clip with narration.

---

## 🎥 45-second launch video — storyboard

Record with QuickTime (**File → New Screen Recording**) or `⌘⇧5`. Keep a large
terminal font (18–20pt) and the window centered.

| # | Duration | On screen | Caption / voiceover |
|---|----------|-----------|---------------------|
| 1 | 0–4s | Black title card: **"How is a $200M app actually built?"** | "You can't see its source code… or can you?" |
| 2 | 4–8s | Finder: `Wispr Flow.app` → Right-click → Show Package Contents | "This is a shipped app. 134 megabytes. Totally opaque." |
| 3 | 8–20s | Terminal: type `murti inspect "/Applications/Wispr Flow.app"` and hit enter; REA runs; report streams out | "One command. It reads the binary itself." |
| 4 | 20–34s | Scroll the report slowly: Identity → Native modules → Windows → Feature signals | "SQLite. Opus audio. Native hotkey. Accessibility paste. gRPC backend." |
| 5 | 34–40s | Zoom on the line: **"no on-device speech model → transcription is cloud"** | "And the twist — it has *no* local speech model. It streams your voice to the cloud." |
| 6 | 40–45s | Cut to README hero + repo URL | "Full architecture. Zero source code. Link in bio." |

**Tips to make it pop:** add a subtle keystroke SFX, speed up REA's wait to ~2s
in the edit, and freeze-frame on step 5. Vertical 9:16 crop for Reels/TikTok/Shorts.

---

## 🐦 X / Twitter thread (build-in-public style)

> **1/**
> I pointed a reverse-engineering engine at a 134MB desktop app I had installed.
>
> In one command it reverse-engineered the entire architecture — no source code.
>
> Here's everything it found 🧵👇
> *[attach the demo GIF/video]*

> **2/**
> The app is Electron under the hood (bundle id gave it away: `com.electron.*`).
>
> So its real code lives in one `app.asar` archive. That's the door in.

> **3/**
> REA mapped 975 files from the binary in seconds. The native addons alone tell
> you most of the story:
> • `node_sqlite3` → local DB
> • `opus` wasm → audio codec
> • `panel_activation` → global hotkey
> • AX windows → it pastes via Accessibility

> **4/**
> The most interesting finding is what's **missing**.
>
> There's NO on-device speech model anywhere in the bundle. Combined with a
> bundled gRPC stack → your dictation audio is streamed to the cloud. 🫢

> **5/**
> I wrapped the whole workflow into a tiny tool called **Murti**.
>
> `murti inspect "/Applications/Any App.app"` → a full architecture report.
>
> Structural metadata only. No source/secrets extracted. For apps you own.

> **6/**
> Built with Claude Code + the REA engine. ~350 lines of Python.
>
> Repo 👉 github.com/technomad641/murti
>
> What app should I teardown next? 👇

---

## 🟠 Reddit post

**Subreddits:** r/SideProject, r/reverseengineering, r/programming, r/electronjs

**Title:**
> I built a tool that reverse-engineers any desktop app's architecture in one command

**Body:**
> I kept wondering how the commercial apps I use are actually built, so I wired a
> reverse-engineering engine (REA) into a tiny Python CLI I'm calling **Murti**.
>
> You point it at a `.app` you have installed and it reads the shipped binary and
> prints a full architecture report: native modules, Electron windows, audio
> pipeline, storage, backend transport, and a list of "feature signals."
>
> As a demo I ran it on a popular dictation app. In one pass it surfaced: Electron
> + webpack, local SQLite, an Opus/AudioWorklet mic pipeline, a native
> global-hotkey addon, macOS Accessibility-based text insertion, and a gRPC
> backend — and notably **no on-device speech model**, which strongly implies
> cloud transcription.
>
> It only surfaces structural metadata (paths, sizes, hashes, inferred purpose) —
> no source, assets, or secrets, and nothing that bypasses licensing/DRM. Meant
> for apps you own or are authorized to analyze.
>
> Repo (MIT): https://github.com/technomad641/murti
> Would love feedback, and suggestions for what to point it at next.

---

## 💼 LinkedIn / short post

> Curious how production desktop apps are architected? I built **Murti** — a
> one-command tool that reads a shipped binary and prints its full architecture
> (native modules, windows, audio pipeline, backend). Ran it on a popular
> dictation app and learned its entire stack — including that it transcribes in
> the cloud, not on-device — without ever opening its source. Built with Claude
> Code + the REA engine. MIT on GitHub.

---

## 🏷️ Hashtags / tags

`#reverseengineering #electron #devtools #buildinpublic #opensource #macOS #infosec`
