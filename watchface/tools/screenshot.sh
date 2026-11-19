#!/usr/bin/env bash
# Grab a full-resolution screenshot from the watch.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
out="${1:-$root/screenshots/watchface-$(date +%Y%m%d-%H%M%S).png}"

mkdir -p "$(dirname "$out")"
adb exec-out screencap -p > "$out"
echo "$out"
