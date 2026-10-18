"""Insert text into whatever app currently has focus.

Strategy: put the text on the clipboard, then synthesize Cmd+V. This is how
most macOS dictation tools insert reliably across apps. Requires the host
process to have Accessibility permission (System Settings > Privacy &
Security > Accessibility).
"""
from __future__ import annotations

import time

from AppKit import NSPasteboard, NSStringPboardType
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)

_V_KEYCODE = 9  # 'v' on a US layout


def set_clipboard(text: str) -> None:
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSStringPboardType)


def paste() -> None:
    """Synthesize Cmd+V."""
    down = CGEventCreateKeyboardEvent(None, _V_KEYCODE, True)
    CGEventSetFlags(down, kCGEventFlagMaskCommand)
    up = CGEventCreateKeyboardEvent(None, _V_KEYCODE, False)
    CGEventSetFlags(up, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, down)
    CGEventPost(kCGHIDEventTap, up)


def insert_text(text: str, restore_clipboard: bool = True) -> None:
    """Paste `text` at the focused cursor, optionally restoring prior clipboard."""
    if not text:
        return
    pb = NSPasteboard.generalPasteboard()
    prior = pb.stringForType_(NSStringPboardType) if restore_clipboard else None
    set_clipboard(text)
    time.sleep(0.05)  # let the pasteboard settle
    paste()
    if restore_clipboard and prior is not None:
        time.sleep(0.15)  # let the target app read the pasteboard first
        set_clipboard(prior)
