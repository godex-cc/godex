#!/usr/bin/env bash
# ============================================================
#  Godex Linux package builder (0.0.1)
#  Overlay approach, same as macOS: the official Codex linux dist
#  (owl-Electron runtime for linux-x64) is the donor; we replace the
#  patched app.asar, icons, desktop entry identity and version stamps.
#  Donor's linux natives (app.asar.unpacked, engine binaries) stay.
#
#  Prerequisites:
#    - donor: unpacked official Codex linux dist (deb/rpm/tar), env DONOR
#    - REPO = this checkout; ASAR = patched app.asar from Windows
#
#  Usage:  REPO=... DONOR=/tmp/codex-dist ASAR=... ./packaging/linux/build-linux.sh
#  Output: packaging/dist/Godex-0.0.1-linux-x64.tar.gz  (+ .deb when the donor
#          came from a deb and dpkg-deb is available)
# ============================================================
set -euo pipefail

: "${REPO:?set REPO to the GodexDesktop checkout}"
: "${DONOR:?set DONOR to the unpacked official Codex linux dist}"
: "${ASAR:=$REPO/app/resources/app.asar}"

VERSION="$(tr -d ' \r\n' < "$REPO/packaging/VERSION")"
STAGE="$REPO/packaging/stage/Godex-$VERSION-linux-x64"
DIST="$REPO/packaging/dist"

[ -d "$DONOR" ] || { echo "donor dist not found: $DONOR" >&2; exit 1; }
[ -f "$ASAR" ] || { echo "patched asar not found: $ASAR" >&2; exit 1; }

echo "==> staging donor dist"
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R "$DONOR/." "$STAGE/"

echo "==> swapping in the patched Godex asar"
# donor layout: <root>/app/resources/app.asar (same owl-electron shape as win)
[ -f "$STAGE/app/resources/app.asar" ] || { echo "donor app/resources/app.asar not found" >&2; exit 1; }
cp "$ASAR" "$STAGE/app/resources/app.asar"

echo "==> rebranding icons + desktop entry"
mkdir -p "$STAGE/share/icons/hicolor"
for s in 16 32 48 64 128 256; do
  mkdir -p "$STAGE/share/icons/hicolor/${s}x${s}/apps"
  cp "$REPO/packaging/icons/godex-$s.png" \
     "$STAGE/share/icons/hicolor/${s}x${s}/apps/godex.png"
done
for desk in "$STAGE"/share/applications/*.desktop; do
  [ -e "$desk" ] || continue
  sed -i 's/^Name=.*/Name=Godex/; s/^Icon=.*/Icon=godex/; s/^Exec=.*/Exec=godex %U/' "$desk"
  mv "$desk" "$STAGE/share/applications/godex.desktop"
done
# binary rename Codex -> Godex (keep executable bit)
for b in "$STAGE"/app/Codex "$STAGE"/Codex; do
  [ -e "$b" ] && mv "$b" "$(dirname "$b")/Godex" && chmod +x "$(dirname "$b")/Godex"
done
find "$STAGE/app/resources" -maxdepth 1 -name 'codex*.png' -delete 2>/dev/null || true

echo "==> version stamps -> 0.0.1"
INI="$STAGE/app/resources/owl-app.ini"
[ -f "$INI" ] && sed -i "s/^AppVersion=.*/AppVersion=$VERSION/" "$INI"

echo "==> tarball"
mkdir -p "$DIST"
tar -C "$STAGE" -czf "$DIST/Godex-$VERSION-linux-x64.tar.gz" .

if command -v dpkg-deb >/dev/null 2>&1 && [ -d "$DONOR/DEBIAN" ]; then
  echo "==> repacking deb (control: godex $VERSION)"
  CONTROL="$STAGE/DEBIAN"
  mkdir -p "$CONTROL"
  printf 'Package: godex\nVersion: %s\nArchitecture: amd64\nMaintainer: Godex\n' "$VERSION" \
    > "$CONTROL/control"
  printf 'Depends: libgtk-3-0, libnss3, libasound2\n' >> "$CONTROL/control"
  dpkg-deb --build "$STAGE" "$DIST/Godex-$VERSION-linux-x64.deb"
fi

echo "==> done: $DIST/Godex-$VERSION-linux-x64.tar.gz"
echo "caveat: runs the donor's official linux engine; do not copy win engine binaries."
