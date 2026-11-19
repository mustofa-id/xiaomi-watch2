#!/usr/bin/env bash
# Build a debug-signed watch face and install it over ADB.
# Usage: ./tools/deploy.sh [watch-ip:port]
set -euo pipefail

cd "$(dirname "$0")/.."

usage() {
    echo "Usage: $0 [watch-ip:port]"
}

if [[ $# -gt 1 ]]; then
    usage >&2
    exit 2
fi

case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
    -*)
        echo "Unknown option: $1" >&2
        usage >&2
        exit 2
        ;;
esac

watch_addr="${1:-${WATCH_ADDR:-}}"
apk="face/build/outputs/apk/debug/face-debug.apk"
adb_target=()

./gradlew --console=plain :face:assembleDebug

if [[ -n "$watch_addr" ]]; then
    echo "Connecting to ${watch_addr}..."
    adb connect "$watch_addr" >/dev/null
    adb_target=(-s "$watch_addr")
fi

if ! adb "${adb_target[@]}" get-state >/dev/null 2>&1; then
    echo "No ADB device is available." >&2
    echo "Wake the watch, connect with 'adb connect <watch-ip>:5555', or pass the address to this script." >&2
    exit 1
fi

adb "${adb_target[@]}" install -r "$apk"

echo
echo "Installed. On the watch: long-press the current face -> pick \"Black\"."
echo "Reinstalls keep the same package, so the face stays selected."
