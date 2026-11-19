#!/usr/bin/env bash
# Xiaomi Watch 2 — apply the documented, reversible user-0 debloat list.
set -uo pipefail

usage() {
  cat <<'EOF'
Usage: ./apply.sh [--dry-run] [--yes]

  --dry-run  Print the target and planned package actions without changing it.
  --yes      Skip the interactive APPLY confirmation.
EOF
}

dry_run=false
assume_yes=false

while (($#)); do
  case "$1" in
    --dry-run) dry_run=true ;;
    --yes) assume_yes=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

PKGS=(
  com.android.vending
  com.xiaomi.wearweather
  com.google.android.wearable.dwf.weather
  com.xiaomi.worldclock
  com.google.android.apps.youtube.music
  com.google.android.apps.messaging
  com.google.android.keep
  com.google.android.apps.walletnfcrel
  com.google.android.clockwork.nfc
  io.port6.watchbridge
  com.google.android.marvin.talkback
  com.android.stk
  com.android.cellbroadcastreceiver
  com.android.cellbroadcastreceiver.module
  com.google.android.inputmethod.latin
)

if ! adb get-state >/dev/null 2>&1; then
  echo "No ADB device is available. Connect the watch first." >&2
  exit 1
fi

model="$(adb shell getprop ro.product.model 2>/dev/null | tr -d '\r')"
device="$(adb shell getprop ro.product.device 2>/dev/null | tr -d '\r')"

printf 'Target: %s (%s)\n\n' "${model:-unknown model}" "${device:-unknown device}"
cat <<'EOF'
WARNING: This disables the Play Store, Gboard, TalkBack, Wallet/NFC, weather,
cell-broadcast/emergency-alert packages, and other optional apps for user 0.
Review the debloat README before continuing.

Packages to disable:
EOF
printf '  - %s\n' "${PKGS[@]}"
printf '  - %s (remove for user 0)\n\n' com.xiaomi.wearos.firebase

if "$dry_run"; then
  echo "Dry run only; no changes were made."
  exit 0
fi

if ! "$assume_yes"; then
  read -r -p "Type APPLY to continue: " confirmation
  if [[ "$confirmation" != "APPLY" ]]; then
    echo "Cancelled; no changes were made."
    exit 1
  fi
fi

for package in "${PKGS[@]}"; do
  printf 'Disabling %s\n' "$package"
  adb shell pm disable-user --user 0 "$package" || true
done

printf 'Removing telemetry for user 0: com.xiaomi.wearos.firebase\n'
adb shell pm uninstall -k --user 0 com.xiaomi.wearos.firebase || true

printf '\nDone. Reboot when convenient with: adb reboot\n'
