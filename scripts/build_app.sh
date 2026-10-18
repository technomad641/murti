#!/bin/zsh
# Build Murti.app with py2app and ad-hoc-sign it so it double-clicks locally.
#
#   scripts/build_app.sh            # fast ALIAS build (this Mac only)
#   scripts/build_app.sh standalone # self-contained bundle (for distribution)
#
# The alias build references your .venv, so it starts instantly and is tiny,
# but only runs on this machine. The standalone build copies Python + deps in
# (large) and is the one you sign + notarize with scripts/sign_notarize.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=./.venv/bin/python
MODE="${1:-alias}"
APP="dist/Murti.app"

[[ -x "$PY" ]] || { echo "No venv at $PY — run: uv venv --python 3.12 .venv && uv pip install -r requirements.txt"; exit 1; }
"$PY" -c "import py2app" 2>/dev/null || { echo "Installing py2app…"; uv pip install --python "$PY" "py2app==0.28.8" "setuptools<81" wheel; }

echo "▸ Cleaning previous build…"
rm -rf build "$APP"

if [[ "$MODE" == "standalone" ]]; then
  echo "▸ Building SELF-CONTAINED bundle (this is large and takes a while)…"
  "$PY" setup_app.py py2app
else
  echo "▸ Building ALIAS bundle (fast; runs on this Mac only)…"
  "$PY" setup_app.py py2app -A
fi

echo "▸ Ad-hoc signing so it launches without a Gatekeeper block…"
codesign --force --sign - "$APP"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

codesign --verify --verbose=2 "$APP"
echo
echo "✓ Built $APP ($MODE build)."
echo "  Double-click it in Finder, or:  open $APP"
[[ "$MODE" == "alias" ]] && echo "  (Alias build — to share with other Macs, run: scripts/build_app.sh standalone)"
