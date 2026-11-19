#!/usr/bin/env bash
# Xiaomi Watch 2 — undo every user-0 package change in apply.sh.
set -uo pipefail

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

for package in "${PKGS[@]}"; do
  printf 'Enabling %s\n' "$package"
  adb shell pm enable --user 0 "$package" 2>/dev/null || true
done

printf 'Restoring com.xiaomi.wearos.firebase\n'
adb shell cmd package install-existing com.xiaomi.wearos.firebase 2>/dev/null || true

printf 'Reselecting Gboard\n'
adb shell ime set \
  com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME \
  2>/dev/null || true

printf '\nDone. Reboot when convenient with: adb reboot\n'
