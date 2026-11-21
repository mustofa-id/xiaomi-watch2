#!/usr/bin/env bash
# Restore native Wi-Fi control without changing the watch's Wi-Fi preference.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./fix-wifi.sh [--dry-run] [--yes]

  --dry-run  Inspect the target and print the repair and rollback commands only.
  --yes      Skip the interactive FIX confirmation.

Use ANDROID_SERIAL to select a device if more than one is attached.
This restores device-wide connectivity mediation; wireless ADB may disconnect.
EOF
}

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

unverified() {
  printf 'Verification incomplete: %s\n' "$1" >&2
  cat >&2 <<'EOF'
Wireless ADB may have disconnected when normal Wi-Fi control resumed.
Wake the watch, enable Wi-Fi if needed, reconnect ADB, and rerun this script.
No automatic radio toggle, rollback, or reboot was attempted.
EOF
  exit 3
}

adb_target() {
  adb -s "$serial" "$@"
}

get_setting() {
  local value
  if ! value="$(adb_target shell settings get "$1" "$2")"; then
    printf 'Could not read %s setting %s.\n' "$1" "$2" >&2
    return 1
  fi
  printf '%s\n' "${value//$'\r'/}"
}

get_wifi_mediator() {
  local dump section
  if ! dump="$(adb_target shell dumpsys WearConnectivityService)"; then
    return 1
  fi
  section="$(printf '%s\n' "${dump//$'\r'/}" | awk '
    /======== WearWifiMediator ========/ { in_wifi = 1; next }
    in_wifi && /^[[:space:]]*======== / { exit }
    in_wifi { print }
  ')"
  if [[ "$section" != *"mWifiSetting="* ||
        ! "$section" =~ mWifiEnabled=(true|false)([[:space:]]|$) ]]; then
    return 1
  fi
  printf '%s\n' "$section"
}

dry_run=false
assume_yes=false

while (($#)); do
  case "$1" in
    --dry-run) dry_run=true ;;
    --yes) assume_yes=true ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

command -v adb >/dev/null 2>&1 || fail "ADB is not installed; install Android SDK platform-tools."
if ! serial="$(adb get-serialno)"; then
  fail "Connect one watch, or set ANDROID_SERIAL to select it."
fi
serial="${serial//$'\r'/}"
[[ -n "$serial" && "$serial" != unknown ]] || fail "No ADB device is available."
[[ "$(adb_target get-state)" == device ]] || fail "The selected ADB device is not online."

model="$(adb_target shell getprop ro.product.model)"
device="$(adb_target shell getprop ro.product.device)"
model="${model//$'\r'/}"
device="${device//$'\r'/}"
printf 'Target: %s (%s)\nADB serial: %s\n\n' "$model" "$device" "$serial"
[[ "$device" == axolotlaxie ]] || fail "This repair is only supported on the tested Xiaomi Watch 2 (axolotlaxie)."

KEYS=(cw_disable_connectivity_mediators cw_disable_wifimediator)
original_values=()
needs_change=false

for key in "${KEYS[@]}"; do
  value="$(get_setting global "$key")" || fail "Could not inspect the developer overrides; no changes were made."
  if [[ "$value" != null && ! "$value" =~ ^[+-]?[0-9]+$ ]]; then
    fail "Unexpected value for $key; no changes were made."
  fi
  original_values+=("$value")
  printf '  %s=%s\n' "$key" "$value"
  if [[ "$value" != 0 && "$value" != null ]]; then
    needs_change=true
  fi
done

wifi_preference="$(get_setting system clockwork_wifi_setting)" || fail "Could not inspect the Wi-Fi preference; no changes were made."
mediator="$(get_wifi_mediator)" || fail "The Wi-Fi controller is unavailable or its dump format is unsupported; no changes were made."
printf '  clockwork_wifi_setting=%s (left unchanged)\n' "$wifi_preference"
if [[ "$mediator" == *"WifiMediator is disabled"* ]]; then
  echo "  Wi-Fi mediation: disabled by a developer override"
else
  echo "  Wi-Fi mediation: enabled"
fi

cat <<'EOF'

WARNING: This clears device-wide developer connectivity overrides, allowing
normal radio and power-saving policies to resume, not only Wi-Fi mediation.
If the saved Wi-Fi preference is Off, wireless ADB may disconnect immediately.
Wi-Fi/Bluetooth preferences, debugging settings, saved networks, and packages
are not changed. The watch will not be rebooted.

Repair:
EOF
for key in "${KEYS[@]}"; do
  printf '  %s -> 0\n' "$key"
done

echo
echo "Rollback commands (save these before applying; they restore the old overrides):"
for index in "${!KEYS[@]}"; do
  key="${KEYS[$index]}"
  value="${original_values[$index]}"
  if [[ "$value" == null ]]; then
    printf '  adb -s %q shell settings delete global %s\n' "$serial" "$key"
  else
    printf '  adb -s %q shell settings put global %s %q\n' "$serial" "$key" "$value"
  fi
done
echo

if "$dry_run"; then
  echo "Dry run only; no changes were made."
  exit 0
fi

if "$needs_change"; then
  if ! "$assume_yes"; then
    confirmation=""
    if ! read -r -p "Type FIX to restore normal connectivity control: " confirmation ||
       [[ "$confirmation" != FIX ]]; then
      echo "Cancelled; no changes were made."
      exit 1
    fi
  fi

  echo "Restoring normal connectivity mediation..."
  # Use one remote shell, clearing the master override last to reduce the risk
  # of losing wireless ADB before both settings have been written.
  if ! adb_target shell 'set -e
settings put global cw_disable_wifimediator 0
settings put global cw_disable_connectivity_mediators 0'; then
    if [[ "$(adb_target get-state 2>/dev/null || true)" != device ]]; then
      unverified "The connection closed during the repair; the writes may be incomplete."
    fi
    fail "Could not update both overrides; changes may be partial. See the rollback commands above."
  fi
else
  echo "No override is enabled; no settings were changed."
fi

# Settings observers run asynchronously. Retry verification only, never writes.
for attempt in 1 2 3; do
  for key in "${KEYS[@]}"; do
    value="$(get_setting global "$key")" || unverified "Could not reread the developer overrides."
    [[ "$value" == 0 || "$value" == null ]] || fail "$key is still $value; normal connectivity control was not restored."
  done
  mediator="$(get_wifi_mediator)" || unverified "Could not inspect the running Wi-Fi controller."
  if [[ "$mediator" != *"WifiMediator is disabled"* ]]; then
    break
  fi
  if [[ "$attempt" == 3 ]]; then
    fail "The overrides are clear, but the controller still reports disabled. A manual restart and recheck may be needed; no reboot was attempted."
  fi
  sleep 1
done

status="$(adb_target shell cmd wifi status)" || unverified "Could not read the actual Wi-Fi radio state."
status="${status//$'\r'/}"
radio_state="${status%%$'\n'*}"
case "$radio_state" in
  "Wifi is enabled"|"Wifi is disabled") ;;
  *) unverified "The Wi-Fi radio status format is unsupported." ;;
esac

printf '\nVerified: native Wi-Fi mediation is enabled.\n%s\n' "$radio_state"
echo "The Wi-Fi preference was left unchanged; an enabled radio is not a repair failure."
echo "Test the switch and leave Wi-Fi Settings after turning it off; wireless ADB may disconnect."
