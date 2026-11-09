#!/bin/zsh
# Builds HA Sync.app (universal, release) into mac/build/.
#
# Environment (all optional):
#   VERSION        app version (CFBundleShortVersionString). Default: the
#                  version in custom_components/mac_sync/manifest.json.
#   BUILD_NUMBER   CFBundleVersion. Default: 1.
#   SIGN_IDENTITY  codesign identity, e.g. "Developer ID Application: Name (TEAMID)".
#                  Default "-" (ad-hoc). A real identity also enables the
#                  hardened runtime and a secure timestamp, as notarization needs.
set -euo pipefail
cd "$(dirname "$0")"

VERSION="${VERSION:-$(python3 -c 'import json;print(json.load(open("../custom_components/mac_sync/manifest.json"))["version"])')}"
BUILD_NUMBER="${BUILD_NUMBER:-1}"
SIGN_IDENTITY="${SIGN_IDENTITY:--}"

ARCHS=(--arch arm64 --arch x86_64)   # universal: Apple silicon + Intel
swift build -c release "${ARCHS[@]}"
BIN="$(swift build -c release "${ARCHS[@]}" --show-bin-path)"

APP="build/HA Sync.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN/HASync" "$APP/Contents/MacOS/HASync"
cp Resources/Info.plist "$APP/Contents/Info.plist"
cp Resources/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $BUILD_NUMBER" "$APP/Contents/Info.plist"

if [[ "$SIGN_IDENTITY" == "-" ]]; then
  codesign --force --sign - --entitlements Resources/HASync.entitlements "$APP"
else
  codesign --force --sign "$SIGN_IDENTITY" --options runtime --timestamp \
    --entitlements Resources/HASync.entitlements "$APP"
fi
codesign --verify --strict "$APP"
echo "Built $APP $VERSION ($BUILD_NUMBER), signed with: $SIGN_IDENTITY"
