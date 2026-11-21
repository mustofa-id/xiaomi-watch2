# Xiaomi Watch 2 debloat scripts

Reversible ADB scripts for disabling optional packages for Android user 0 on a
Xiaomi Watch 2. Root access and bootloader unlocking are not required.

> [!CAUTION]
> Review the complete package list before running the script. It disables the
> Play Store, on-watch keyboard, TalkBack, Wallet/NFC, weather, and
> cell-broadcast components. Depending on your firmware and region, this can
> remove accessibility features, emergency alerts, payments, app updates, and
> text input. You are responsible for deciding whether those tradeoffs are
> appropriate for your watch.

The scripts were tested on a Xiaomi Watch 2 (`axolotlaxie`) running Wear OS 5 /
Android 14. Package availability can differ across firmware versions and
regions. Package commands only affect user 0; they do not modify the system partition.
The standalone Wi-Fi repair below instead restores device-wide developer
settings; it does not run the package debloat list.

## Prerequisites

1. Enable Developer options and Wireless debugging on the watch.
2. Connect with `adb connect <watch-ip>:5555`.
3. If more than one Android device is attached, set `ANDROID_SERIAL` first.
4. Read the package list and rollback instructions below.

Confirm the connected target:

```bash
adb get-state
adb shell getprop ro.product.model
adb shell getprop ro.product.device
```

## Preview and apply

Print the detected device and planned actions without changing anything:

```bash
./apply.sh --dry-run
```

Apply interactively. The script requires typing `APPLY` before it proceeds:

```bash
./apply.sh
```

For deliberate non-interactive use:

```bash
./apply.sh --yes
```

Package-specific failures are reported but do not stop the remaining actions,
which helps across firmware variants where a package may be absent.

## Changes

The following packages are disabled with `pm disable-user --user 0`:

| Package | Feature affected |
|---|---|
| `com.android.vending` | Google Play Store and app updates |
| `com.xiaomi.wearweather` | Xiaomi weather |
| `com.google.android.wearable.dwf.weather` | Google watch-face weather data |
| `com.xiaomi.worldclock` | Xiaomi world clock |
| `com.google.android.apps.youtube.music` | YouTube Music |
| `com.google.android.apps.messaging` | Google Messages |
| `com.google.android.keep` | Google Keep |
| `com.google.android.apps.walletnfcrel` | Google Wallet |
| `com.google.android.clockwork.nfc` | Wear OS NFC provider |
| `io.port6.watchbridge` | Third-party BLE bridge |
| `com.google.android.marvin.talkback` | TalkBack accessibility service |
| `com.android.stk` | SIM toolkit |
| `com.android.cellbroadcastreceiver` | Cell-broadcast/emergency alerts |
| `com.android.cellbroadcastreceiver.module` | Cell-broadcast module |
| `com.google.android.inputmethod.latin` | Gboard/on-watch keyboard |

`com.xiaomi.wearos.firebase` is a persistent Xiaomi system app. The script
removes it for user 0 with `pm uninstall -k --user 0`; the APK remains on the
system partition and can be restored with `install-existing`.

Disabling the Play Store does **not** disable Google Play Services
(`com.google.android.gms`). Features that depend specifically on Store updates,
in-app purchases, or licensing may still stop working.

## Roll back

Restore every package and reselect Gboard:

```bash
./rollback.sh
adb reboot
```

Restore only selected features if preferred:

```bash
# Play Store
adb shell pm enable --user 0 com.android.vending

# Keyboard
adb shell pm enable --user 0 com.google.android.inputmethod.latin
adb shell ime set com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME

# Cell broadcast / emergency alerts
adb shell pm enable --user 0 com.android.cellbroadcastreceiver
adb shell pm enable --user 0 com.android.cellbroadcastreceiver.module
```

## Repair Wi-Fi that stays on

If the Wi-Fi tile and Settings show Off but the radio remains connected, a
developer override may be bypassing Wear OS connectivity control. The watch's
Wi-Fi mediator checks **both** of these global settings:

| Setting | Effect when nonzero |
|---|---|
| `cw_disable_connectivity_mediators` | Disables native connectivity mediation, including Wi-Fi |
| `cw_disable_wifimediator` | Disables Wi-Fi mediation specifically |

Clearing only the Wi-Fi-specific override is not enough while the master
override is enabled. The service's diagnostic message may mention only the
Wi-Fi-specific setting.

`fix-wifi.sh` is a separate utility for the tested Xiaomi Watch 2
(`axolotlaxie`). It pins the selected ADB target, rejects other devices, shows
the current overrides and Wi-Fi preference, and prints exact rollback commands
before making changes. It honors `ANDROID_SERIAL` for device selection.

Preview without changing the watch:

```bash
./fix-wifi.sh --dry-run
```

Apply interactively by typing `FIX`, or deliberately skip confirmation:

```bash
./fix-wifi.sh
./fix-wifi.sh --yes
```

> [!WARNING]
> This restores **device-wide native connectivity policies**, not just Wi-Fi
> control. Automatic radio and power-saving policies can resume. The script
> does not toggle Wi-Fi or Bluetooth preferences, change debugging settings,
> forget networks, change packages, or reboot. If your stored Wi-Fi preference
> is already Off, restoring control can immediately disconnect wireless ADB.

When an override is enabled, the script clears both to `0` in one remote shell,
with the master override last. Already-clear overrides are left alone. It then
checks the saved values, the running `WearWifiMediator`, and `cmd wifi status`.
Only read-only verification is retried while settings observers catch up.

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Verified normal mediation, or a completed dry run |
| `1` | Preflight failure, cancellation, failed write, or controller mismatch |
| `2` | Invalid command-line option |
| `3` | Verification incomplete, including an ADB disconnect |

An ADB disconnect is **not** automatically reported as success. Wake the watch,
turn Wi-Fi on if needed, reconnect, and rerun the script to verify. It will not
automatically restore the bypass or reboot to recover the connection.

After a verified repair, test Off and return to the watch face. The Wi-Fi
settings page can itself request Wi-Fi while open. Turn Wi-Fi back on if you
need ADB for further checks. A currently enabled radio is not a failed repair;
the script restores control rather than forcing the radio off.

### Undo the repair

Save the exact rollback commands printed **before applying** and run them only
if you intentionally want the old developer overrides back. An originally
unset value is restored with `settings delete`, not `settings put ... null`.
Restoring a nonzero override may recreate the original Wi-Fi problem.
`rollback.sh` restores packages only; it does not undo this standalone repair.

### Test without a watch

The tests use a mock ADB executable and temporary state, never a real device:

```bash
python3 -B -m unittest discover -s tests -v
```

## ADB reconnection

The watch may suspend Wi-Fi while its screen is off. Wake it or place it on its
charger, then use:

```bash
adb mdns services
adb connect <watch-ip>:5555
```

## License

These scripts are licensed under Apache-2.0; see [`../LICENSE`](../LICENSE).
