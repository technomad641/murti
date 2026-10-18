"""py2app build configuration for Murti.app.

Two ways to build (see scripts/build_app.sh for the wrapper):

  # Fast, local, double-clickable on THIS Mac (references the venv):
  ./.venv/bin/python setup_app.py py2app -A

  # Fully self-contained bundle for distribution (large; pairs with
  # scripts/sign_notarize.sh):
  ./.venv/bin/python setup_app.py py2app

The result is dist/Murti.app. Sign it with scripts/sign_notarize.sh once you
have an Apple "Developer ID Application" certificate; until then the build
scripts ad-hoc-sign it so it launches locally without a Gatekeeper block.
"""
from setuptools import setup

APP = ["launch_murti.py"]

# Bundled alongside the code so the dashboard + icon resolve inside the bundle.
DATA_FILES = [
    ("", ["ui"]),
    ("", ["murti/assets"]),
]

PLIST = {
    "CFBundleName": "Murti",
    "CFBundleDisplayName": "Murti",
    "CFBundleIdentifier": "com.rajat.murti",
    "CFBundleShortVersionString": "0.1.0",
    "CFBundleVersion": "0.1.0",
    "LSMinimumSystemVersion": "13.0",
    # Regular app: shows in the Dock with its window (the menu-bar icon stays
    # too). The app also sets the activation policy at runtime.
    "LSUIElement": False,
    # TCC usage strings shown in the system permission prompts.
    "NSMicrophoneUsageDescription":
        "Murti records your voice to transcribe it into text.",
    "NSAppleEventsUsageDescription":
        "Murti pauses music and ducks other audio while you dictate.",
    "NSHumanReadableCopyright": "© Rajat Singh. MIT licensed.",
}

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "murti/assets/Murti.icns",
    "plist": PLIST,
    # Make sure these are importable from the frozen app. In alias mode (-A)
    # they are referenced from the venv; in a standalone build they are copied.
    "packages": [
        "murti", "rumps", "pynput", "objc", "Foundation", "AppKit", "WebKit",
        "Quartz",
    ],
    "includes": ["murti.app", "murti.dashboard", "murti.pipeline"],
    # Heavy, optional, or lazily-imported deps: don't let a missing one abort
    # the freeze. Transcription models are imported on first use.
    "excludes": ["tkinter", "setuptools", "pip", "wheel"],
}

setup(
    app=APP,
    name="Murti",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
