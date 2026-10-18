"""Dictation app: a visible window **and** a menu-bar icon.

Press the global hotkey (default Cmd+Alt+D) to start recording; press again to
stop, transcribe, and paste the result into the focused app. You can also use
the on-screen window (Start/Stop button + toggles) or the menu-bar 🎙️ menu.
"""
from __future__ import annotations

import threading

import objc
import rumps
from AppKit import (
    NSApplication,
    NSBackingStoreBuffered,
    NSButton,
    NSFont,
    NSPopUpButton,
    NSScrollView,
    NSTextField,
    NSTextView,
    NSThread,
    NSOperationQueue,
)
from Foundation import NSObject
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
    from AppKit import NSBezelStyleRounded
except ImportError:  # pragma: no cover
    NSBezelStyleRounded = 1
NSBezelBorder = 2


def _on_main(fn):
    """Run a UI update on the main thread (safe from worker threads)."""
    if NSThread.isMainThread():
        fn()
    else:
        NSOperationQueue.mainQueue().addOperationWithBlock_(fn)


class DictationWindow(NSObject):
    """The visible window: status, Start/Stop, toggles, and last result."""

    def initWithApp_(self, app):
        self = objc.super(DictationWindow, self).init()
        if self is None:
            return None
        self.app = app
        self._build()
        return self

    # ------------------------------------------------------------- building
    @objc.python_method
    def _label(self, text, frame, bold=False, size=13):
        tf = NSTextField.alloc().initWithFrame_(frame)
        tf.setStringValue_(text)
        tf.setBezeled_(False)
        tf.setDrawsBackground_(False)
        tf.setEditable_(False)
        tf.setSelectable_(False)
        tf.setFont_(NSFont.boldSystemFontOfSize_(size) if bold
                    else NSFont.systemFontOfSize_(size))
        self.window.contentView().addSubview_(tf)
        return tf

    @objc.python_method
    def _checkbox(self, title, frame, action, on):
        cb = NSButton.alloc().initWithFrame_(frame)
        cb.setButtonType_(NSButtonTypeSwitch)
        cb.setTitle_(title)
        cb.setState_(1 if on else 0)
        cb.setTarget_(self)
        cb.setAction_(action)
        self.window.contentView().addSubview_(cb)
        return cb

    @objc.python_method
    def _build(self):
        style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
                 | NSWindowStyleMaskMiniaturizable)
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (440, 380)), style, NSBackingStoreBuffered, False)
        win.setTitle_("Murti")
        win.setReleasedWhenClosed_(False)
        win.center()
        self.window = win
        win.setDelegate_(self)

        s = self.app.settings
        self._label("Murti", ((20, 345), (400, 24)), bold=True, size=17)
        self.status_label = self._label("Idle — press Start or ⌘⌥D",
                                         ((20, 318), (400, 20)))

        self.start_btn = NSButton.alloc().initWithFrame_(((20, 272), (400, 36)))
        self.start_btn.setTitle_("Start dictation")
        self.start_btn.setBezelStyle_(NSBezelStyleRounded)
        self.start_btn.setTarget_(self)
        self.start_btn.setAction_("startStop:")
        win.contentView().addSubview_(self.start_btn)

        self.translate_cb = self._checkbox(
            "Translate", ((20, 236), (200, 22)), "toggleTranslate:",
            s.translate_enabled)
        self.roman_cb = self._checkbox(
            "Romanized Hindi", ((220, 236), (210, 22)), "toggleScript:",
            s.hindi_script == "romanized")

        self._label("Target:", ((20, 203), (55, 22)))
        self.lang_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            ((78, 200), (160, 26)), False)
        self.lang_popup.addItemsWithTitles_(LANGUAGES)
        self.lang_popup.selectItemWithTitle_(s.target_language)
        self.lang_popup.setTarget_(self)
        self.lang_popup.setAction_("setLanguage:")
        win.contentView().addSubview_(self.lang_popup)

        self._label("Last result:", ((20, 172), (400, 18)))
        scroll = NSScrollView.alloc().initWithFrame_(((20, 44), (400, 122)))
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(NSBezelBorder)
        tv = NSTextView.alloc().initWithFrame_(((0, 0), (400, 122)))
        tv.setEditable_(False)
        tv.setFont_(NSFont.systemFontOfSize_(13))
        scroll.setDocumentView_(tv)
        win.contentView().addSubview_(scroll)
        self.text_view = tv

        self._label("Hotkey ⌘⌥D (needs Input Monitoring). Transcription is local.",
                    ((20, 16), (400, 18)), size=11)

    # -------------------------------------------------------------- actions
    def startStop_(self, sender):
        self.app.toggle_recording(None)

    def toggleTranslate_(self, sender):
        self.app.act_set_translate(bool(sender.state()))

    def toggleScript_(self, sender):
        self.app.act_set_script(bool(sender.state()))

    def setLanguage_(self, sender):
        self.app.act_set_target(sender.titleOfSelectedItem())

    # window delegate: hide instead of destroy, so "Show window" can re-open
    def windowShouldClose_(self, sender):
        sender.orderOut_(None)
        return False

    # ------------------------------------------------------------- view ops
    @objc.python_method
    def show(self):
        self.window.makeKeyAndOrderFront_(None)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    @objc.python_method
    def syncControls(self):
        s = self.app.settings
        self.translate_cb.setState_(1 if s.translate_enabled else 0)
        self.roman_cb.setState_(1 if s.hindi_script == "romanized" else 0)
        self.lang_popup.selectItemWithTitle_(s.target_language)

    def setStatusText_(self, text):
        self.status_label.setStringValue_(text)

    def setStartTitle_(self, text):
        self.start_btn.setTitle_(text)

    def setLastText_(self, text):
        self.text_view.setString_(text or "")


class DictationApp(rumps.App):
    def __init__(self):
        super().__init__(IDLE, quit_button=None)
        self.settings = Settings.load()
        self.pipeline: Pipeline | None = None  # built lazily (model load is slow)
        self.recorder = None
        self.media = MediaController()
        self._busy = False

        # live dashboard server (serves ui/ + a JSON API over the real engine)
        self.dashboard_url = None
        try:
            from .dashboard import serve
            self._httpd, self.dashboard_url = serve()
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
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyRegular)
        self.win.show()

    # ----------------------------------------------------------------- hotkey
    def _start_hotkey(self):
        def on_activate():
            # pynput callback runs on its own thread; defer to a worker.
            self.toggle_recording(None)

        try:
            hk = keyboard.GlobalHotKeys({self.settings.hotkey: on_activate})
            hk.daemon = True
            hk.start()
        except Exception as e:  # noqa: BLE001
            # Usually missing Input Monitoring permission. App still works via
            # the window's Start button or the menu item.
            rumps.notification(
                "Murti",
                "Global hotkey unavailable",
                "Grant Input Monitoring in System Settings, or use the window. "
                f"({e})",
            )

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
