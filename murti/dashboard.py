"""Local dashboard server — serves ui/ and a tiny JSON API over the real engine.

Everything is 127.0.0.1-only and backed by the same on-device Settings /
Insights / Dictionary the dictation pipeline uses, so the dashboard shows and
edits *live* state. No external network, no auth surface.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .config import Settings
from .insights import Insights
from .vocabulary import Dictionary
from . import devices

UI_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")


def build_state() -> dict:
    s = Settings.load()
    ins = Insights.load()
    d = Dictionary.load()
    try:
        dev = devices.list_input_devices()
    except Exception:  # noqa: BLE001
        dev = []
    return {
        "settings": asdict(s),
        "insights": ins.summary(),
        "dictionary": {"terms": sorted(d.terms), "auto_learn": s.auto_learn},
        "devices": dev,
    }


def apply_settings(patch: dict) -> dict:
    s = Settings.load()
    for k, v in (patch or {}).items():
        if k in s.__dataclass_fields__:
            setattr(s, k, v)
    s.save()
    return {"ok": True}


def add_word(word: str) -> dict:
    d = Dictionary.load()
    if word and word.strip():
        d.add(word.strip())
        d.save()
    return {"ok": True, "terms": sorted(d.terms)}


class _Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=UI_DIR, **k)

    def log_message(self, *a):  # keep the app quiet
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw or b"{}")
        except Exception:  # noqa: BLE001
            return {}

    def do_GET(self):
        if self.path.split("?")[0] == "/api/state":
            return self._json(build_state())
        if self.path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        data = self._read_json()
        if path == "/api/settings":
            return self._json(apply_settings(data))
        if path == "/api/dictionary":
            return self._json(add_word(data.get("word", "")))
        return self._json({"ok": False, "error": "not found"}, 404)


def serve(host: str = "127.0.0.1", port: int = 0):
    """Start the dashboard server on a background thread. Returns (httpd, url)."""
    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.daemon_threads = True
    bound_port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://{host}:{bound_port}/"


if __name__ == "__main__":  # manual run: python -m murti.dashboard
    import webbrowser

    _httpd, url = serve()
    print(f"Murti dashboard → {url}")
    webbrowser.open(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
