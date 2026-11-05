#!/usr/bin/env bash
# Builds a signed release APK for a specific client flavor without EAS and without expo prebuild.
#
# Usage:
#   mobile/scripts/build-client.sh [--print-apk-name] <slug>
#
# Environment variables:
#   API_BASE_URL    API the app talks to (default: https://api.cashback-qr.poscenter.kz)
#   KEYS_DIR        folder with release.keystore + keystore.env (default: ~/.cashback-one-keys)
#   JAVA_HOME       JDK 17 (default: ~/.jdks/zulu17*)
#   ABIS            CPU architectures (default: arm64-v8a,armeabi-v7a)
#   MIN_FREE_KB     Minimum free disk space in KB (default: 3000000 ~ 3 GB)
#   FORCE_SPACE     Set to 1 to bypass disk space check
set -euo pipefail

PRINT_ONLY=0
SLUG=""

for arg in "$@"; do
  case "$arg" in
    --print-apk-name)
      PRINT_ONLY=1
      ;;
    -*)
      echo "Unknown option: $arg" >&2
      echo "Usage: $0 [--print-apk-name] <slug>" >&2
      exit 1
      ;;
    *)
      if [ -z "$SLUG" ]; then
        SLUG="$arg"
      else
        echo "Unexpected argument: $arg" >&2
        echo "Usage: $0 [--print-apk-name] <slug>" >&2
        exit 1
      fi
      ;;
  esac
done

if [ -z "$SLUG" ]; then
  echo "Usage: $0 [--print-apk-name] <slug>" >&2
  exit 1
fi

cd "$(dirname "$0")/.."

CLIENT_CONFIG="clients/${SLUG}/client.json"
if [ ! -f "$CLIENT_CONFIG" ]; then
  echo "Error: Client config not found: $CLIENT_CONFIG" >&2
  exit 1
fi

VERSION="$(node -p "require('./app.json').expo.version")"
APK_NAME="$(node -p "require('./${CLIENT_CONFIG}').apk_name || '${SLUG}'")"

if ! [[ "$APK_NAME" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  echo "Error: Invalid apk_name in $CLIENT_CONFIG: $APK_NAME (must match ^[a-z0-9]+(-[a-z0-9]+)*$)" >&2
  exit 1
fi

APK_FILENAME="${APK_NAME}-${VERSION}.apk"

if [ "$PRINT_ONLY" = "1" ]; then
  echo "$APK_FILENAME"
  exit 0
fi

# 1. Check free disk space
MIN_FREE_KB="${MIN_FREE_KB:-3000000}"
FREE_KB="$(df -k "$HOME" | awk 'NR==2 {print $4}')"
if [ "$FREE_KB" -lt "$MIN_FREE_KB" ] && [ "${FORCE_SPACE:-0}" != "1" ]; then
  echo "Error: Not enough disk space. Free: ${FREE_KB} KB, required: ${MIN_FREE_KB} KB (~3 GB)" >&2
  echo "Use FORCE_SPACE=1 to bypass if building high-priority client." >&2
  exit 1
fi

# 2. Production env
export EXPO_PUBLIC_CLIENT="$SLUG"
export NODE_ENV=production
export EXPO_PUBLIC_API_BASE_URL="${API_BASE_URL:-https://api.cashback-qr.poscenter.kz}"

# 3. Unset demo and insecure flags
unset EXPO_PUBLIC_DEMO || true
unset EXPO_PUBLIC_ALLOW_INSECURE_HTTP || true

# 4. Load release signing keys in subshell / env
KEYS_DIR="${KEYS_DIR:-$HOME/.cashback-one-keys}"
if [ ! -f "$KEYS_DIR/release.keystore" ] || [ ! -f "$KEYS_DIR/keystore.env" ]; then
  echo "Error: Missing $KEYS_DIR/release.keystore or keystore.env" >&2
  exit 1
fi

# Tool paths
if [ -z "${JAVA_HOME:-}" ]; then
  JAVA_HOME="$(ls -d "$HOME"/.jdks/zulu17*/Contents/Home 2>/dev/null | head -1)"
fi
export JAVA_HOME
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ABIS="${ABIS:-arm64-v8a,armeabi-v7a}"

# 5. Assemble flavor
FLAVOR="$(tr '[:lower:]' '[:upper:]' <<< "${SLUG:0:1}")${SLUG:1}"
TASK="assemble${FLAVOR}Release"
echo "=== Building client '${SLUG}' (flavor: ${FLAVOR}, task: app:${TASK}) ==="

(
  set -a
  # shellcheck disable=SC1090
  . "$KEYS_DIR/keystore.env"
  set +a
  export CASHBACK_STORE_FILE="$KEYS_DIR/release.keystore"

  cd android
  ./gradlew "app:${TASK}" \
    -PreactNativeArchitectures="$ABIS" \
    --no-daemon \
    --max-workers=1 \
    -Dorg.gradle.parallel=false \
    --console=plain
)

# 6. Copy APK to mobile/dist/<apk_name>-<version>.apk
OUTPUT_DIR="android/app/build/outputs/apk/${SLUG}/release"
SRC_APK="$(ls -t "$OUTPUT_DIR"/*.apk 2>/dev/null | head -1 || true)"

if [ -z "$SRC_APK" ] || [ ! -f "$SRC_APK" ]; then
  echo "Error: Generated APK not found in $OUTPUT_DIR" >&2
  exit 1
fi

mkdir -p dist
DEST_APK="dist/${APK_FILENAME}"

if [ -f "$DEST_APK" ]; then
  echo "Target APK already exists: $DEST_APK (not overwriting with cp -n)"
else
  cp -n "$SRC_APK" "$DEST_APK"
  echo "Copied APK to $DEST_APK"
fi

echo "=== Build completed successfully for ${SLUG} ==="
ls -lh "$DEST_APK"
shasum -a 256 "$DEST_APK"
