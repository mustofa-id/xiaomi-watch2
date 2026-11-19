#!/usr/bin/env bash
# Validate watchface.xml against the official Watch Face Format schema.
# Usage: ./tools/validate.sh [format-version]   (default: 1)
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
version="${1:-1}"
jar="${XDG_CACHE_HOME:-$HOME/.cache}/wff-validator.jar"

if [ ! -f "$jar" ]; then
    echo "Downloading wff-validator.jar..."
    curl -sL -o "$jar" "https://github.com/google/watchface/releases/download/latest/wff-validator.jar"
fi

java -jar "$jar" "$version" "$root/face/src/main/res/raw/watchface.xml"
