#!/bin/zsh
# Builds HA Sync.app (release) and ad-hoc signs it.
set -euo pipefail
cd "$(dirname "$0")"
ARCHS=(--arch arm64 --arch x86_64)   # universal: Apple silicon + Intel
swift build -c release "${ARCHS[@]}"
BIN="$(swift build -c release "${ARCHS[@]}" --show-bin-path)"
APP="build/HA Sync.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN/HASync" "$APP/Contents/MacOS/HASync"
cp Resources/Info.plist "$APP/Contents/Info.plist"
cp Resources/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
codesign --force --sign - --entitlements Resources/HASync.entitlements "$APP"
echo "Built $APP"
