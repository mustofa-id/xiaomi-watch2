#!/usr/bin/env bash
# Normalize a clean, square on-device screenshot as the picker preview.
# Usage: ./tools/make-preview.sh path/to/screenshot.png
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 path/to/clean-screenshot.png" >&2
    exit 2
fi

source_image="$1"
output="face/src/main/res/drawable/preview.png"

if [[ ! -f "$source_image" ]]; then
    echo "Screenshot not found: $source_image" >&2
    exit 1
fi

read -r width height < <(identify -format '%w %h' "$source_image")
if [[ "$width" -ne "$height" ]]; then
    echo "Preview source must be square; got ${width}x${height}." >&2
    exit 1
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

magick "$source_image" \
    -auto-orient -resize 466x466! -strip \
    -colorspace sRGB -type TrueColor -depth 8 \
    -define png:color-type=2 "png:$tmp"

install -m 0644 "$tmp" "$output"
echo "wrote $output"
