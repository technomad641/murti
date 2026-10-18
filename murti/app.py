"""Murti: a menu-bar app with a native window hosting the live dashboard.

Press the global hotkey (default Cmd+Alt+D) to start recording; press again to
stop, transcribe, and paste the result into the focused app. The app window is
the Murti dashboard (a WKWebView over the local engine); the menu-bar 🎙️ icon
shows status and reopens it.
"""
from __future__ import annotations

import threading

import objc
import rumps
from AppKit import (
    NSApplication,
    NSBackingStoreBuffered,
    NSColor,
    NSImage,
    NSThread,
    NSOperationQueue,
)
from Foundation import NSObject, NSURL, NSURLRequest
from pynput import keyboard

from .config import Settings
from .pipeline import Pipeline
from .media import MediaController

LANGUAGES = ["English", "Hindi", "Spanish", "French", "German"]
IDLE = "🎙️"
RECORDING = "🔴"
BUSY = "⏳"

# --- AppKit constants, with numeric fallbacks across pyobjc versions ---------
try:  # activation policy: 0 = Regular (Dock icon + focusable windows)
    from AppKit import NSApplicationActivationPolicyRegular
except ImportError:  # pragma: no cover
    NSApplicationActivationPolicyRegular = 0
try:
    from AppKit import (
        NSWindow,
        NSWindowStyleMaskTitled,
        NSWindowStyleMaskClosable,
        NSWindowStyleMaskMiniaturizable,
    )
except ImportError:  # pragma: no cover
    from AppKit import NSWindow
    NSWindowStyleMaskTitled, NSWindowStyleMaskClosable, NSWindowStyleMaskMiniaturizable = 1, 2, 4
try:
    from AppKit import NSButtonTypeSwitch
except ImportError:  # pragma: no cover
    NSButtonTypeSwitch = 3
try:
    from AppKit import (NSViewWidthSizable, NSViewHeightSizable,
                        NSWindowStyleMaskResizable)
except ImportError:  # pragma: no cover
    NSViewWidthSizable, NSViewHeightSizable, NSWindowStyleMaskResizable = 2, 16, 8
try:
    from WebKit import WKWebView, WKWebViewConfiguration
    _HAVE_WEBKIT = True
except ImportError:  # pragma: no cover
    _HAVE_WEBKIT = False


def _on_main(fn):
    """Run a UI update on the main thread (safe from worker threads)."""
    if NSThread.isMainThread():
        fn()
    else:
        NSOperationQueue.mainQueue().addOperationWithBlock_(fn)


class DictationWindow(NSObject):
    """A native window hosting the Murti dashboard (WKWebView over the live engine)."""

    def initWithApp_(self, app):
        self = objc.super(DictationWindow, self).init()
        if self is None:
            return None
        self.app = app
        self.webview = None
        self._build()
        return self

    @objc.python_method
    def _build(self):
        style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
                 | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable)
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (1160, 780)), style, NSBackingStoreBuffered, False)
        win.setTitle_("Murti")
        win.setReleasedWhenClosed_(False)
        win.setMinSize_((900, 600))
        win.setBackgroundColor_(
            NSColor.colorWithSRGBRed_green_blue_alpha_(0.937, 0.914, 0.867, 1.0))
        win.center()
        self.window = win
        win.setDelegate_(self)
        content = win.contentView()

        if _HAVE_WEBKIT:
            cfg = WKWebViewConfiguration.alloc().init()
            web = WKWebView.alloc().initWithFrame_configuration_(
                content.bounds(), cfg)
            web.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
            content.addSubview_(web)
            self.webview = web
            self._load()

    @objc.python_method
    def _load(self):
        if self.webview is None:
            return
        if self.app.dashboard_url:
            url = NSURL.URLWithString_(self.app.dashboard_url)
        else:  # fallback: load the bundled HTML straight from disk
            import os
            path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ui", "index.html")
            url = NSURL.fileURLWithPath_(path)
        self.webview.loadRequest_(NSURLRequest.requestWithURL_(url))

    def windowShouldClose_(self, sender):
        sender.orderOut_(None)   # hide; the menu can re-open it
        return False

    @objc.python_method
    def show(self):
        self._load()  # refresh to the latest live state each time it opens
        self.window.makeKeyAndOrderFront_(None)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    # kept as harmless no-ops so DictationApp's status/sync calls still work;
    # the dashboard reflects live state over the /api, so these do nothing now
    @objc.python_method
    def syncControls(self):
        pass

    def setStatusText_(self, text):
        pass

    def setStartTitle_(self, text):
        pass

    def setLastText_(self, text):
        pass


class DictationApp(rumps.App):
    def __init__(self):
        super().__init__(IDLE, quit_button=None)
        self.settings = Settings.load()
        self.pipeline: Pipeline | None = None  # built lazily (model load is slow)
        self.recorder = None
        self.media = MediaController()
        self._busy = False
        self._hk = None  # the global-hotkey listener (rebindable)

        # live dashboard server (serves ui/ + a JSON API over the real engine)
        self.dashboard_url = None
        try:
            from .dashboard import serve
            self._httpd, self.dashboard_url = serve(on_change=self._on_settings_changed)
        except Exception:  # noqa: BLE001 — dashboard is optional
            pass

        # --- menu bar ---
        self.translate_item = rumps.MenuItem("Translate", callback=self.toggle_translate)
        self.translate_item.state = self.settings.translate_enabled
        self.roman_item = rumps.MenuItem("Romanized Hindi", callback=self.toggle_script)
        self.roman_item.state = self.settings.hindi_script == "romanized"
        self.lang_menu = rumps.MenuItem("Target language")
        for lang in LANGUAGES:
            mi = rumps.MenuItem(lang, callback=self.set_language)
            mi.state = lang == self.settings.target_language
            self.lang_menu.add(mi)

        self.menu = [
            rumps.MenuItem("Show window", callback=self.show_window),
            rumps.MenuItem("Open Dashboard…", callback=self.open_dashboard),
            rumps.MenuItem("Start / Stop dictation", callback=self.toggle_recording),
            None,
            self.translate_item,
            self.lang_menu,
            self.roman_item,
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]

        # --- visible window ---
        self.win = DictationWindow.alloc().initWithApp_(self)

        self._start_hotkey()

        # Show the window + Dock icon shortly after the run loop starts.
        self._show_timer = rumps.Timer(self._first_show, 0.4)
        self._show_timer.start()

    def _first_show(self, timer):
        timer.stop()
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        self._set_dock_icon(app)
        self.win.show()

    def _set_dock_icon(self, app):
        """Set the Dock/app icon at runtime (works for `run.sh` too, not just the bundle)."""
        import os
        icon = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
        try:
            img = NSImage.alloc().initWithContentsOfFile_(icon)
            if img:
                app.setApplicationIconImage_(img)
        except Exception:  # noqa: BLE001
            pass

    # ----------------------------------------------------------------- hotkey
    def _start_hotkey(self):
        self._bind_hotkey()

    def _bind_hotkey(self):
        """(Re)register the global hotkey from self.settings.hotkey."""
        try:
            if self._hk is not None:
                self._hk.stop()
        except Exception:  # noqa: BLE001
            pass
        self._hk = None

        def on_activate():
            # pynput callback runs on its own thread; defer to a worker.
            self.toggle_recording(None)

        try:
            hk = keyboard.GlobalHotKeys({self.settings.hotkey: on_activate})
            hk.daemon = True
            hk.start()
            self._hk = hk
        except Exception as e:  # noqa: BLE001
            # Usually missing Input Monitoring permission, or an invalid combo.
            # App still works via the menu item.
            rumps.notification(
                "Murti", "Global hotkey unavailable",
                "Grant Input Monitoring in System Settings, or pick another "
                f"shortcut. ({e})",
            )

    def _on_settings_changed(self, patch):
        """Called by the dashboard after a settings write — keep the app in sync."""
        old_hotkey = self.settings.hotkey
        self.settings = Settings.load()
        if (patch or {}).get("hotkey") and self.settings.hotkey != old_hotkey:
            _on_main(self._bind_hotkey)   # rebind to the new combo immediately

    # --------------------------------------------------------------- status
    def _set_state(self, emoji, status_text, start_title):
        self.title = emoji

        def upd():
            self.win.setStatusText_(status_text)
            self.win.setStartTitle_(start_title)

        _on_main(upd)

    # --------------------------------------------------------------- actions
    def toggle_recording(self, _sender):
        if self._busy:
            return
        if self.recorder is None:
            from .recorder import Recorder

            self.recorder = Recorder()

        if not self.recorder.recording:
            try:
                self.recorder.start()
            except Exception as e:  # noqa: BLE001
                rumps.notification(
                    "Murti", "Microphone unavailable",
                    f"Grant Microphone permission in System Settings. ({e})",
                )
                self._set_state(IDLE, f"Microphone unavailable ({e})", "Start dictation")
                return
            self.media.on_record_start(self.settings.pause_media,
                                       self.settings.mute_others)
            self._set_state(RECORDING, "● Recording… click Stop or press ⌘⌥D",
                            "Stop dictation")
        else:
            audio = self.recorder.stop()
            self.media.on_record_stop(self.settings.pause_media,
                                      self.settings.mute_others)
            self._set_state(BUSY, "Transcribing…", "Working…")
            self._busy = True
            threading.Thread(target=self._run_pipeline, args=(audio,), daemon=True).start()

    def _run_pipeline(self, audio):
        final = ""
        try:
            if self.pipeline is None:
                self.pipeline = Pipeline(self.settings)
            final = self.pipeline.dictate(audio, insert=True)
        except Exception as e:  # noqa: BLE001
            rumps.notification("Murti", "Error", str(e))
            final = f"[error] {e}"
        finally:
            self._busy = False
            text = final or "(no speech detected)"
            _on_main(lambda: self.win.setLastText_(text))
            self._set_state(IDLE, "Idle — press Start or ⌘⌥D", "Start dictation")

    # setting toggles (shared by window + menu, keep both in sync) -----------
    def act_set_translate(self, enabled):
        self.settings.translate_enabled = enabled
        self.settings.save()
        self.translate_item.state = enabled
        self.win.syncControls()

    def act_set_script(self, romanized):
        self.settings.hindi_script = "romanized" if romanized else "devanagari"
        self.settings.save()
        self.roman_item.state = romanized
        self.win.syncControls()

    def act_set_target(self, lang):
        self.settings.target_language = lang
        self.settings.save()
        for mi in self.lang_menu.values():
            mi.state = mi.title == lang
        self.win.syncControls()

    # menu-bar callbacks route through the shared setters --------------------
    def toggle_translate(self, _sender):
        self.act_set_translate(not self.settings.translate_enabled)

    def toggle_script(self, _sender):
        self.act_set_script(self.settings.hindi_script != "romanized")

    def set_language(self, sender):
        self.act_set_target(sender.title)

    def show_window(self, _sender):
        self.win.show()

    def open_dashboard(self, _sender=None):
        """Open the full black-&-white dashboard (Meetings, Insights, Account…)."""
        import os
        import subprocess

        target = self.dashboard_url or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "ui", "index.html")
        try:
            subprocess.Popen(["open", target])
        except Exception as e:  # noqa: BLE001
            rumps.notification("Murti", "Could not open dashboard", str(e))


def main():
    NSApplication.sharedApplication().setActivationPolicy_(
        NSApplicationActivationPolicyRegular)
    DictationApp().run()


if __name__ == "__main__":
    main()
