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
regions. Commands only affect user 0; they do not modify the system partition.

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

## ADB reconnection

The watch may suspend Wi-Fi while its screen is off. Wake it or place it on its
charger, then use:

```bash
adb mdns services
adb connect <watch-ip>:5555
```

## License

These scripts are licensed under Apache-2.0; see [`../LICENSE`](../LICENSE).
