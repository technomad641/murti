#!/usr/bin/env python3
"""Murti — X-ray a desktop app's architecture using REA.

Point it at a macOS ``.app`` bundle, an Electron ``app.asar``, or any artifact
REA can open, and it prints (and optionally writes) a readable architecture
report: app identity, native modules, process/window structure, integrity
flags, feature signals, and REA's own suggested next probes.

It is a thin, friendly front-end over the REA reverse-engineering CLI
(``rea-agents``) — the point is to show how much REA can tell you about an
opaque binary in a single pass.

Scope: this tool only surfaces STRUCTURAL metadata (file paths, sizes, hashes,
and *inferred* purpose). It does not extract, decompile, or print source code,
assets, or secrets. Use it only on software you own or are authorized to
analyze.

Usage:
    python teardown.py "/Applications/Some App.app"
    python teardown.py app.asar -o report.md
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

REA_PACKAGE = "rea-agents@6.4.0"


# --------------------------------------------------------------------------- #
# Driving the REA CLI
# --------------------------------------------------------------------------- #
def _node_bin_dir() -> str | None:
    """Find an nvm node bin dir that has npx (REA needs a modern Node)."""
    candidates = sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin")))
    for d in reversed(candidates):  # prefer the newest installed version
        if os.path.exists(os.path.join(d, "npx")):
            return d
    return None


def rea_command() -> tuple[list[str], dict]:
    """Return (argv_prefix, env) for invoking REA.

    Prefers an installed ``rea`` on PATH; otherwise falls back to
    ``npx -y rea-agents@…``. Ensures Node is on PATH for either case.
    """
    env = dict(os.environ)
    node_dir = _node_bin_dir()
    if node_dir and node_dir not in env.get("PATH", ""):
        env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")

    rea = shutil.which("rea", path=env["PATH"])
    if rea:
        return [rea], env

    npx = shutil.which("npx", path=env["PATH"])
    if not npx:
        sys.exit("error: could not find `rea` or `npx`. Install Node (>=24) and "
                 "REA (npm i -g rea-agents), or ensure nvm is set up.")
    return [npx, "-y", REA_PACKAGE], env


def run_inspect(target: str) -> dict:
    """Run `rea inspect-artifact <target>` and return parsed JSON."""
    argv, env = rea_command()
    cmd = argv + ["inspect-artifact", target,
                  "--integrity-policy", "record-and-continue",
                  "--format", "json"]
    print(f"• running REA: {' '.join(argv)} inspect-artifact …", file=sys.stderr)
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        sys.exit(f"error: REA inspect-artifact failed (exit {proc.returncode}).\n"
                 f"{proc.stderr.strip()[:2000]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        sys.exit(f"error: could not parse REA JSON output: {e}")


# --------------------------------------------------------------------------- #
# Target resolution
# --------------------------------------------------------------------------- #
def resolve_target(path: str) -> tuple[str, str, dict]:
    """Resolve a user-supplied path to the best artifact for REA.

    Returns (artifact_path, kind, bundle_info). ``kind`` is 'electron-asar',
    'app-executable', or 'file'. For a ``.app`` bundle we prefer its
    ``app.asar`` (Electron) and otherwise fall back to the main executable.
    """
    p = Path(path).expanduser()
    if not p.exists():
        sys.exit(f"error: no such path: {p}")

    bundle_info: dict = {}
    if p.suffix == ".app" and p.is_dir():
        info_plist = p / "Contents" / "Info.plist"
        if info_plist.exists():
            try:
                with open(info_plist, "rb") as fh:
                    pl = plistlib.load(fh)
                bundle_info = {
                    "name": pl.get("CFBundleName") or pl.get("CFBundleDisplayName"),
                    "version": pl.get("CFBundleShortVersionString"),
                    "identifier": pl.get("CFBundleIdentifier"),
                    "executable": pl.get("CFBundleExecutable"),
                }
            except Exception:  # noqa: BLE001 — Info.plist is best-effort
                pass
        asar = p / "Contents" / "Resources" / "app.asar"
        if asar.exists():
            return str(asar), "electron-asar", bundle_info
        exe = bundle_info.get("executable")
        if exe and (p / "Contents" / "MacOS" / exe).exists():
            return str(p / "Contents" / "MacOS" / exe), "app-executable", bundle_info
        return str(p), "file", bundle_info

    return str(p), "file", bundle_info


# --------------------------------------------------------------------------- #
# Parsing REA's inventory
# --------------------------------------------------------------------------- #
PATH_KEYS = ("logical_path", "path", "name")
SIZE_KEYS = ("declared_size", "size", "bytes", "byte_size")


def _norm(data: dict) -> dict:
    return data.get("normalized_result", data) or {}


def collect_files(data) -> list[dict]:
    """Recursively collect file-ish records {path, size} from the graph.

    Version-tolerant: any dict carrying a path-like string plus a size is
    treated as a file node. Deduped by path.
    """
    found: dict[str, int | None] = {}
    # Don't mistake the artifact's own identity metadata for its contents.
    skip_keys = {"subject", "provider", "analysis_profile", "environment"}

    def walk(obj):
        if isinstance(obj, dict):
            path = next((obj[k] for k in PATH_KEYS
                         if isinstance(obj.get(k), str) and ("/" in obj[k]
                         or "." in obj[k])), None)
            size = next((obj[k] for k in SIZE_KEYS
                         if isinstance(obj.get(k), (int, float))), None)
            if path and (size is not None or path not in found):
                # keep the largest size we see for a path
                prev = found.get(path)
                found[path] = size if prev is None else (
                    max(prev, size) if size is not None else prev)
            for k, v in obj.items():
                if k not in skip_keys:
                    walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(_norm(data) if isinstance(data, dict) else data)
    return [{"path": k, "size": v} for k, v in sorted(found.items())]


def classify(files: list[dict]) -> dict:
    """Group inventory paths into architecture-relevant buckets (heuristic)."""
    out = {
        "native_addons": [], "wasm": [], "windows_libs": [], "workers": [],
        "renderer_windows": [], "main_bundles": [], "audio_assets": [],
        "has_package_json": False, "has_node_modules": False,
    }
    win_re = re.compile(r"(?:^|/)\.webpack/renderer/([^/]+)/index\.html$")
    for f in files:
        p, size = f["path"], f["size"]
        base = p.rsplit("/", 1)[-1]
        if base == "package.json":
            out["has_package_json"] = True
        if "/node_modules/" in p or p.startswith("node_modules"):
            out["has_node_modules"] = True
        if p.endswith(".node"):
            out["native_addons"].append(f)
        elif p.endswith(".wasm"):
            out["wasm"].append(f)
        elif p.endswith((".dll", ".exe")):
            out["windows_libs"].append(f)
        if ".worker.js" in base or base.endswith("worker.js"):
            out["workers"].append(f)
        m = win_re.search(p)
        if m:
            out["renderer_windows"].append(m.group(1))
        if re.search(r"\.webpack/main/[^/]+\.js$", p) and "worker" not in base:
            out["main_bundles"].append(f)
        if p.endswith((".wav", ".mp3", ".m4a")) or (
                p.endswith((".mp4", ".webm")) and re.search(
                    r"wave|audio|record|dictation|voice", p, re.I)):
            out["audio_assets"].append(f)
    out["renderer_windows"] = sorted(set(out["renderer_windows"]))
    return out


FEATURE_SIGNALS = {
    "Microphone / audio capture": r"recorderworklet|audioworklet|\bmic\b|capture.*audio|record",
    "Audio codec (Opus etc.)": r"opus|\bpcm\b|codec|encoder\.worker",
    "On-device speech model (ASR)": r"whisper|onnx|ggml|vosk|\.gguf|model.*\.(bin|onnx|pt)|coreml",
    "Global hotkey / activation panel": r"hotkey|shortcut|panel_activation|global.?key|accelerator",
    "Text insertion / Accessibility (AX)": r"accessibility|ax[-_]inspect|ax-inspect|\bpaste\b|\binject\b",
    "Local database": r"sqlite|leveldb|\.db\b|indexeddb|realm",
    "Backend networking": r"grpc|\.proto\b|graphql|websocket|socket\.io",
    "Auto-update": r"autoupdat|updater|squirrel|electron-updater",
    "Menu-bar / tray / overlay": r"\btray\b|menubar|overlay|status(bar|_)|hud",
}


def _clean_ex(path: str) -> str:
    """Show the last two path segments (drops the noisy `.webpack/` prefix)."""
    segs = [s for s in path.split("/") if s and s != ".webpack"]
    return "/".join(segs[-2:]) if len(segs) >= 2 else (segs[-1] if segs else path)


def scan_features(files: list[dict]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for f in files:
        p = f["path"]
        for label, pat in FEATURE_SIGNALS.items():
            if re.search(pat, p, re.I):
                ex = _clean_ex(p)
                lst = hits.setdefault(label, [])
                if len(lst) < 4 and ex not in lst:
                    lst.append(ex)
    return hits


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _fmt_size(n):  # simple, readable
    if not isinstance(n, (int, float)):
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}".rstrip("0").rstrip(".") if unit != "B" else f"{int(n)} B"
        n /= 1024


def render(data: dict, target: str, kind: str, bundle: dict) -> str:
    nr = _norm(data)
    subject = data.get("subject") or nr.get("subject") or {}
    provider = data.get("provider") or {}
    files = collect_files(data)
    buckets = classify(files)
    features = scan_features(files)

    contradictions = nr.get("contradictions") or []
    next_probes = nr.get("next_probes") or []
    hypotheses = nr.get("hypotheses") or []
    coverage = nr.get("coverage") or {}

    L: list[str] = []
    name = (bundle.get("name") or subject.get("name")
            or Path(target).name)
    L.append(f"# Architecture X-ray — {name}")
    L.append("")
    L.append("_Generated by [Murti](https://github.com/technomad641/murti) "
             "driving the REA reverse-engineering CLI. Structural metadata only — "
             "no source, assets, or secrets are extracted. Purpose labels are "
             "inferred._")
    L.append("")

    # Identity -------------------------------------------------------------
    L.append("## Identity")
    L.append("")
    L.append(f"- **Target:** `{target}`")
    L.append(f"- **Kind:** {kind}")
    if bundle.get("version"):
        L.append(f"- **Version:** {bundle['version']}")
    if bundle.get("identifier"):
        L.append(f"- **Bundle id:** `{bundle['identifier']}`")
    sha = (subject.get("digest") or {}).get("sha256")
    if sha:
        L.append(f"- **SHA-256:** `{sha}`")
    if subject.get("format"):
        L.append(f"- **Format:** {subject['format']}")
    if provider.get("name"):
        L.append(f"- **Analyzed by:** {provider['name']} "
                 f"v{provider.get('version', '?')}")
    L.append(f"- **Files inventoried:** {len(files)}")
    L.append("")

    # Stack ----------------------------------------------------------------
    is_electron = (kind == "electron-asar" or buckets["renderer_windows"]
                   or buckets["main_bundles"])
    L.append("## Stack")
    L.append("")
    if is_electron:
        L.append("- **Electron app** (webpack bundles under `.webpack/`).")
    if buckets["has_package_json"]:
        L.append("- Ships a `package.json` manifest.")
    L.append("")

    # Native modules -------------------------------------------------------
    natives = buckets["native_addons"] + buckets["wasm"] + buckets["windows_libs"]
    if natives:
        L.append("## Native modules & addons")
        L.append("")
        role_map = [
            (r"sqlite", "local SQLite database"),
            (r"panel|activation", "native panel / hotkey-activation"),
            (r"crypt32", "Windows credential/cert store"),
            (r"opus", "Opus audio codec"),
            (r"keytar|keychain", "OS keychain / secret storage"),
            (r"ffmpeg|libav", "media decode/encode"),
            (r"roots\.(exe|pem)", "TLS root certificates (gRPC)"),
            (r"[0-9a-f]{16,}\.node$", "webpack-emitted native addon (name hashed)"),
        ]
        # Collapse the big bundled Jabra/.NET SDK into one summary row.
        jabra = [f for f in natives
                 if re.search(r"jabra-device-connector|gnaudio", f["path"], re.I)]
        rest = [f for f in natives if f not in jabra]
        L.append("| File | Size | Likely role (inferred) |")
        L.append("|------|------|------------------------|")
        for f in rest:
            role = next((r for pat, r in role_map
                         if re.search(pat, f["path"], re.I)), "—")
            L.append(f"| `{f['path'].rsplit('/', 1)[-1]}` | "
                     f"{_fmt_size(f['size'])} | {role} |")
        if jabra:
            total = sum(f["size"] or 0 for f in jabra)
            L.append(f"| _{len(jabra)} files under_ `jabra-device-connector/` | "
                     f"{_fmt_size(total)} | Jabra headset SDK (bundled .NET + "
                     "native, Bluetooth/USB device control) |")
        L.append("")

    # Processes & windows --------------------------------------------------
    if buckets["renderer_windows"] or buckets["main_bundles"] or buckets["workers"]:
        L.append("## Processes & windows")
        L.append("")
        if buckets["main_bundles"]:
            big = sorted(buckets["main_bundles"],
                         key=lambda f: f["size"] or 0, reverse=True)[:5]
            L.append("**Main process bundles:** "
                     + ", ".join(f"`{f['path'].rsplit('/', 1)[-1]}` "
                                 f"({_fmt_size(f['size'])})" for f in big))
            L.append("")
        if buckets["workers"]:
            L.append("**Worker threads:** "
                     + ", ".join(sorted({f["path"].rsplit("/", 1)[-1]
                                         for f in buckets["workers"]})))
            L.append("")
        if buckets["renderer_windows"]:
            L.append(f"**Renderer windows ({len(buckets['renderer_windows'])}):** "
                     + ", ".join(f"`{w}`" for w in buckets["renderer_windows"]))
            L.append("")

    # Feature signals ------------------------------------------------------
    if features:
        L.append("## Feature signals (inferred from paths)")
        L.append("")
        for label, paths in features.items():
            ex = ", ".join(f"`{p}`" for p in paths)
            L.append(f"- **{label}** — e.g. {ex}")
        if "On-device speech model (ASR)" not in features:
            L.append("- _No on-device speech model found in the inventory_ — "
                     "transcription is likely cloud/streaming (notable design "
                     "signal).")
        L.append("")

    # Integrity ------------------------------------------------------------
    if contradictions:
        L.append("## Integrity flags")
        L.append("")
        L.append(f"REA flagged **{len(contradictions)}** file(s) whose declared "
                 "hash ≠ observed bytes (common for re-signed unpacked native "
                 "binaries; REA marks them untrusted rather than trusting them):")
        L.append("")
        for c in contradictions[:10]:
            stmt = c.get("statement")
            if stmt:
                L.append(f"- {stmt}")
            else:
                lp = c.get("logical_path") or c.get("path") or "?"
                L.append(f"- `{lp.rsplit('/', 1)[-1]}`")
        L.append("")

    # REA next steps -------------------------------------------------------
    if hypotheses or next_probes:
        L.append("## What REA suggests next")
        L.append("")
        for h in hypotheses[:3]:
            txt = h.get("statement") or h.get("description") or json.dumps(h)[:160]
            L.append(f"- _Hypothesis:_ {txt}")
        for pr in next_probes[:4]:
            tool = pr.get("operation") or pr.get("tool") or ""
            txt = (pr.get("rationale") or pr.get("reason")
                   or pr.get("description") or "")
            if not txt and not tool:
                txt = json.dumps(pr)[:160]
            L.append(f"- _Next probe:_ {('`' + tool + '` — ') if tool else ''}{txt}")
        L.append("")

    if coverage:
        status = coverage.get("status", "?")
        L.append(f"> Coverage: **{status}** "
                 f"({coverage.get('substeps_completed', '?')} substep(s)).")
        L.append("")

    return "\n".join(L)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="murti",
        description="X-ray a desktop app's architecture using REA.")
    p.add_argument("path", help="Path to a .app bundle, app.asar, or binary.")
    p.add_argument("-o", "--out", help="Write the Markdown report to this file.")
    p.add_argument("--raw", help="Also save REA's raw JSON to this path.")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    target, kind, bundle = resolve_target(args.path)
    print(f"• target: {target}  (kind: {kind})", file=sys.stderr)
    data = run_inspect(target)
    if args.raw:
        Path(args.raw).write_text(json.dumps(data, indent=2))
        print(f"• raw JSON → {args.raw}", file=sys.stderr)
    report = render(data, target, kind, bundle)
    if args.out:
        Path(args.out).write_text(report)
        print(f"• report → {args.out}", file=sys.stderr)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
