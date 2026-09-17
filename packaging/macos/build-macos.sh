#!/usr/bin/env bash
# ============================================================
#  Godex macOS package builder (0.0.1)
#  Overlay approach: clone the OFFICIAL Codex.app (the owl-Electron runtime
#  for darwin-arm64/x64, which we cannot rebuild from Windows), then replace
#  everything that is Godex: the patched app.asar, the brand icons, the
#  identity/version metadata. The donor's platform-native pieces
#  (app.asar.unpacked natives, engine binaries, Electron framework) stay.
#
#  Prerequisites (run ON a Mac):
#    - donor app, e.g. /Applications/Codex.app        (env DONOR to override)
#    - this repository checked out at $REPO
#    - the patched asar built on Windows and copied here:
#        REPO/app/resources/app.asar                  (env ASAR to override)
#        (asar JS is platform-independent; app.asar.unpacked natives are
#         NOT inside the asar, so the donor's mac natives remain active)
#    - Xcode CLT (codesign) and hdiutil (ship with macOS)
#
#  Usage:  REPO=/path/to/GodexDesktop DONOR=/Applications/Codex.app \
#          ASAR=$REPO/app/resources/app.asar ./packaging/macos/build-macos.sh
#  Output: packaging/dist/Godex-0.0.1-macos.dmg
# ============================================================
set -euo pipefail

: "${REPO:?set REPO to the GodexDesktop checkout}"
: "${DONOR:?set DONOR to the official Codex.app path}"
: "${ASAR:=$REPO/app/resources/app.asar}"

VERSION="$(tr -d ' \r\n' < "$REPO/packaging/VERSION")"
STAGE="$REPO/packaging/stage/Godex-$VERSION-macos"
DIST="$REPO/packaging/dist"
APP="$STAGE/Godex.app"

[ -d "$DONOR" ] || { echo "donor app not found: $DONOR" >&2; exit 1; }
[ -f "$ASAR" ] || { echo "patched asar not found: $ASAR" >&2; exit 1; }
grep -q '"version": "0.0.1"' <(python3 -c "import zipfile" 2>/dev/null; true) 2>/dev/null || true

echo "==> staging donor app"
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R "$DONOR" "$APP"

echo "==> swapping in the patched Godex asar"
RES="$APP/Contents/Resources"
[ -f "$RES/app.asar" ] || { echo "donor has no Contents/Resources/app.asar" >&2; exit 1; }
cp "$ASAR" "$RES/app.asar"

echo "==> rebranding icons (keep tray assets, swap the app icon)"
for icns in "$RES"/*.icns; do
  [ -e "$icns" ] || continue
  case "$(basename "$icns")" in
    *tray*) : ;;
    *) cp "$REPO/packaging/icons/godex.icns" "$icns" ;;
  esac
done

echo "==> stamping identity + version 0.0.1"
PLIST="$APP/Contents/Info.plist"
plutil -replace CFBundleName -string "Godex" "$PLIST"
plutil -replace CFBundleDisplayName -string "Godex" "$PLIST"
plutil -replace CFBundleExecutable -string "Godex" "$PLIST"
plutil -replace CFBundleShortVersionString -string "$VERSION" "$PLIST"
plutil -replace CFBundleVersion -string "$VERSION" "$PLIST"
BIN_DIR="$APP/Contents/MacOS"
mv "$BIN_DIR/Codex" "$BIN_DIR/Godex" 2>/dev/null || true
# NOTE: CFBundleIdentifier stays com.openai.codex on purpose - the app sets
# that AppUserModelID/AUMID at runtime and taskbar/dock grouping expects it.

echo "==> ad-hoc codesign (unsigned builds would be killed by Gatekeeper)"
codesign --force --deep --sign - "$APP"

echo "==> packaging dmg"
mkdir -p "$DIST"
hdiutil create -volname "Godex $VERSION" -srcfolder "$STAGE" \
  -ov -format UDZO "$DIST/Godex-$VERSION-macos.dmg"

echo "==> done: $DIST/Godex-$VERSION-macos.dmg"
echo "caveat: this build runs the donor's official mac engine; our Windows"
echo "engine (resources/godex + godex.exe) is win32-only and must NOT be copied."
