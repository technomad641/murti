#!/bin/zsh
# Developer-ID-sign, notarize, and staple dist/Murti.app so it runs on ANY Mac
# with no Gatekeeper warning. Run scripts/build_app.sh standalone first.
#
# One-time setup (needs a paid Apple Developer account):
#   1. Get a "Developer ID Application" certificate (Xcode ▸ Settings ▸
#      Accounts ▸ Manage Certificates ▸ + ▸ Developer ID Application), or
#      download it from developer.apple.com and double-click to install.
#   2. Create an app-specific password at appleid.apple.com, then store a
#      reusable notary credential in your keychain:
#        xcrun notarytool store-credentials murti-notary \
#          --apple-id "you@example.com" --team-id "TEAMID" --password "xxxx-xxxx-xxxx-xxxx"
#   3. Run this script.
#
# Override the identity/profile with env vars if needed:
#   IDENTITY="Developer ID Application: Your Name (TEAMID)" NOTARY_PROFILE=murti-notary scripts/sign_notarize.sh
set -euo pipefail
cd "$(dirname "$0")/.."

APP="dist/Murti.app"
PROFILE="${NOTARY_PROFILE:-murti-notary}"
IDENTITY="${IDENTITY:-}"

[[ -d "$APP" ]] || { echo "✗ $APP not found. Build it first:  scripts/build_app.sh standalone"; exit 1; }

# A notarizable app must be self-contained; alias builds symlink to your venv.
if find "$APP/Contents/Resources" -maxdepth 2 -type l 2>/dev/null | grep -q .; then
  echo "⚠  $APP looks like an ALIAS build (contains symlinks to your source/venv)."
  echo "   Notarization needs a self-contained bundle. Rebuild with:"
  echo "     scripts/build_app.sh standalone"
  exit 1
fi

# notarytool ships with full Xcode (not the Command Line Tools alone).
if ! xcrun --find notarytool >/dev/null 2>&1; then
  echo "✗ 'notarytool' not found. Install full Xcode (not just Command Line Tools),"
  echo "  then: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
  exit 1
fi

# Find a Developer ID Application certificate if one wasn't supplied.
if [[ -z "$IDENTITY" ]]; then
  IDENTITY=$(security find-identity -v -p codesigning | awk -F\" '/Developer ID Application/{print $2; exit}')
fi
if [[ -z "$IDENTITY" ]]; then
  echo "✗ No 'Developer ID Application' certificate in your keychain."
  echo "  You need a paid Apple Developer account — see the setup notes at the"
  echo "  top of this script, then re-run it."
  exit 1
fi
echo "▸ Signing with: $IDENTITY"

codesign --force --deep --options runtime --timestamp \
  --entitlements packaging/entitlements.plist \
  --sign "$IDENTITY" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

echo "▸ Zipping for notarization…"
ZIP="dist/Murti.zip"
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"

echo "▸ Submitting to Apple notary service (this can take a few minutes)…"
xcrun notarytool submit "$ZIP" --keychain-profile "$PROFILE" --wait

echo "▸ Stapling the notarization ticket…"
xcrun stapler staple "$APP"

echo "▸ Final Gatekeeper check:"
spctl -a -t exec -vv "$APP"

echo
echo "✓ $APP is Developer-ID-signed, notarized and stapled — ready to distribute."
