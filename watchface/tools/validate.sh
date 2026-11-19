#!/usr/bin/env bash
# Validate watchface.xml against the official Watch Face Format schema.
# Usage: ./tools/validate.sh [format-version]   (default: 1)
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
version="${1:-1}"
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}"
jar="$cache_dir/wff-validator.jar"

mkdir -p "$cache_dir"

if [[ ! -s "$jar" ]]; then
    echo "Downloading wff-validator.jar..."
    tmp="$(mktemp "$cache_dir/wff-validator.jar.XXXXXX")"
    trap 'rm -f "$tmp"' EXIT

    curl --fail --silent --show-error --location --retry 3 \
        --output "$tmp" \
        "https://github.com/google/watchface/releases/latest/download/wff-validator.jar"

    mv "$tmp" "$jar"
    trap - EXIT
fi

java -jar "$jar" "$version" "$root/face/src/main/res/raw/watchface.xml"
