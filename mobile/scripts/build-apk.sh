#!/usr/bin/env bash
# Builds a signed release APK of the customer app without EAS.
#
#   API_BASE_URL   API the app talks to (default: production)
#   KEYS_DIR       folder with release.keystore + keystore.env (default: ~/.cashback-one-keys)
#   JAVA_HOME      JDK 17 (default: first ~/.jdks/zulu17*)
#   ABIS           CPU architectures (default: arm64-v8a,armeabi-v7a)
#
# The android/ folder is generated (expo prebuild) and not committed. Output: mobile/dist/cashback-one-<version>.apk
set -euo pipefail
cd "$(dirname "$0")/.."

cleanup() {
  git checkout -- package.json 2>/dev/null || true
}
trap cleanup EXIT

API_BASE_URL="${API_BASE_URL:-https://api.cashback-qr.poscenter.kz}"
KEYS_DIR="${KEYS_DIR:-$HOME/.cashback-one-keys}"
ABIS="${ABIS:-arm64-v8a,armeabi-v7a}"
if [ -z "${JAVA_HOME:-}" ]; then JAVA_HOME="$(ls -d "$HOME"/.jdks/zulu17*/Contents/Home 2>/dev/null | head -1)"; fi
export JAVA_HOME
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"

[ -f "$KEYS_DIR/release.keystore" ] && [ -f "$KEYS_DIR/keystore.env" ] || { echo "Missing $KEYS_DIR/release.keystore or keystore.env" >&2; exit 1; }
# shellcheck disable=SC1091
set -a; . "$KEYS_DIR/keystore.env"; set +a
export CASHBACK_STORE_FILE="$KEYS_DIR/release.keystore"

echo "=== Running expo prebuild ==="
npx expo prebuild --platform android --no-install --clean
git checkout -- package.json 2>/dev/null || true

echo "=== Patching android/app/build.gradle for release signing ==="
python3 - android/app/build.gradle <<'PY'
import sys
import re

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

# 1. Add release signingConfig block
if "signingConfigs.release" not in src or "CASHBACK_STORE_FILE" not in src:
    release_signing = """    signingConfigs {
        release {
            storeFile file(System.getenv('CASHBACK_STORE_FILE'))
            storePassword System.getenv('CASHBACK_STORE_PASSWORD')
            keyAlias System.getenv('CASHBACK_KEY_ALIAS')
            keyPassword System.getenv('CASHBACK_KEY_PASSWORD')
        }
        debug {"""
    src = src.replace("    signingConfigs {\n        debug {", release_signing, 1)

# 2. In buildTypes.release, change signingConfig from debug to release
pattern = r'(buildTypes\s*\{[\s\S]*?release\s*\{[\s\S]*?signingConfig\s+)signingConfigs\.debug'
src = re.sub(pattern, r'\g<1>signingConfigs.release', src, count=1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

# Assertions to ensure proper patching
assert "storeFile file(System.getenv('CASHBACK_STORE_FILE'))" in src, "Missing release signingConfig block"
assert re.search(r'buildTypes\s*\{[\s\S]*?release\s*\{[\s\S]*?signingConfig\s+signingConfigs\.release', src), "buildTypes.release not using signingConfigs.release"
print("build.gradle successfully patched for release signing.")
PY

VERSION="$(node -p "require('./app.json').expo.version")"
echo "=== Building release APK for version $VERSION (ABIS: $ABIS) ==="

(cd android && EXPO_PUBLIC_API_BASE_URL="$API_BASE_URL" NODE_ENV=production \
  ./gradlew assembleRelease -PreactNativeArchitectures="$ABIS" --no-daemon)

mkdir -p dist
OUTPUT_APK="dist/cashback-one-$VERSION.apk"
cp android/app/build/outputs/apk/release/app-release.apk "$OUTPUT_APK"

BUILD_TOOLS="$(ls -d "$ANDROID_HOME"/build-tools/* 2>/dev/null | sort -V | tail -1)"
echo "=== Verifying signature with apksigner ($BUILD_TOOLS/apksigner) ==="
"$BUILD_TOOLS/apksigner" verify --print-certs "$OUTPUT_APK"

echo "=== Package Badging ($BUILD_TOOLS/aapt) ==="
"$BUILD_TOOLS/aapt" dump badging "$OUTPUT_APK" | grep -E "package|versionName|sdkVersion|targetSdkVersion" || true

echo "=== Result ==="
ls -lh "$OUTPUT_APK"
echo "Build complete: $OUTPUT_APK"

CLEANUP_BUILD="${CLEANUP_BUILD:-1}"
if [ "$CLEANUP_BUILD" = "1" ]; then
  echo "=== Cleaning temporary build artifacts (saving disk space) ==="
  rm -rf android/app/build android/.gradle
fi
