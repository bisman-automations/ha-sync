#!/bin/zsh
# Builds HA Sync.app (release) and ad-hoc signs it.
set -euo pipefail
cd "$(dirname "$0")"
swift build -c release
APP="build/HA Sync.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp .build/release/HASync "$APP/Contents/MacOS/HASync"
cp Resources/Info.plist "$APP/Contents/Info.plist"
codesign --force --sign - --entitlements Resources/HASync.entitlements "$APP"
echo "Built $APP"
