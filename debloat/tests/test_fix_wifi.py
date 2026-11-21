"""Exercise fix-wifi.sh with a stateful fake ADB, never a real device."""

import copy
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "fix-wifi.sh"
MASTER = "cw_disable_connectivity_mediators"
WIFI = "cw_disable_wifimediator"

FAKE_ADB = r'''
import json
import os
from pathlib import Path
import shlex
import sys

path = Path(os.environ["MOCK_ADB_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
serial = None
if args[:1] == ["-s"]:
    serial, args = args[1], args[2:]
state["calls"].append({"serial": serial, "args": args})

def save():
    path.write_text(json.dumps(state))

def fail(message):
    save()
    print(message, file=sys.stderr)
    sys.exit(1)

def setting(namespace, key):
    return str(state["settings"].get(namespace, {}).get(key, "null"))

def disabled():
    return any(setting("global", key) not in ("0", "null") for key in (
        "cw_disable_connectivity_mediators", "cw_disable_wifimediator"))

def execute(command):
    if command[:2] == ["getprop", "ro.product.model"]:
        return state["model"]
    if command[:2] == ["getprop", "ro.product.device"]:
        return state["device"]
    if command[:2] == ["settings", "get"]:
        namespace, key = command[2:]
        if state.get("fail_read_key") == key and (
            not state.get("read_failure_after_write") or state["writes"]
        ):
            fail("Could not read settings")
        return setting(namespace, key)
    if command[:2] == ["settings", "put"]:
        namespace, key, value = command[2:]
        if namespace != "global" or key not in (
            "cw_disable_connectivity_mediators", "cw_disable_wifimediator"
        ) or value != "0":
            fail("Unexpected setting mutation")
        if state.get("fail_put_key") == key:
            fail("Permission denied")
        if state.get("silent_put_failure") == key:
            return "SecurityException: write denied"
        state["settings"][namespace][key] = value
        state["writes"].append([namespace, key, value])
        if not disabled():
            state["radio_enabled"] = setting("system", "clockwork_wifi_setting") not in (
                "off", "off_airplane"
            )
            state["settings"]["global"]["wifi_on"] = "1" if state["radio_enabled"] else "0"
        if state.get("disconnect_after_count") == len(state["writes"]):
            state["online"] = False
            fail("Connection closed during remote shell")
        save()
        return ""
    if command == ["dumpsys", "WearConnectivityService"]:
        if not state.get("service_available", True) or (
            state.get("service_lost_after_write") and state["writes"]
        ):
            return "Can't find service: WearConnectivityService"
        is_disabled = disabled() or state.get("controller_stuck", False)
        if not disabled() and state.get("stale_reads", 0):
            state["stale_reads"] -= 1
            is_disabled = True
        warning = "  WifiMediator is disabled by developer setting.\n" if is_disabled else ""
        enabled = str(state["radio_enabled"]).lower()
        preference = setting("system", "clockwork_wifi_setting")
        footer = "  ======== WearWifiScanMediator ========\n"
        if state.get("unrelated_warning"):
            footer += "  WifiMediator is disabled in an unrelated section.\n"
        return (
            "======== WearConnectivityService ========\n"
            "  ======== WearWifiMediator ========\n" + warning +
            f"  mWifiSetting={preference} mWifiEnabled={enabled} mDeviceEnabled=true\n" +
            footer
        )
    if command == ["cmd", "wifi", "status"]:
        if state.get("radio_status"):
            return state["radio_status"]
        return ("Wifi is enabled" if state["radio_enabled"] else "Wifi is disabled") + (
            '\nWifiInfo: SSID: "test-network", BSSID: <test-only>'
        )
    fail(f"Unexpected remote command: {command!r}")

if args == ["get-serialno"]:
    if not state["online"]:
        fail("No devices/emulators found")
    selected = os.environ.get("ANDROID_SERIAL")
    if state.get("multiple_devices") and not selected:
        fail("More than one device/emulator")
    if selected and selected != state["serial"]:
        fail("Selected device not found")
    output = state["serial"]
elif serial != state["serial"]:
    fail("Every command after target selection must pin the same serial")
elif not state["online"]:
    fail("Device offline")
elif args == ["get-state"]:
    output = "device"
elif args[:1] == ["shell"]:
    commands = args[1:]
    if len(commands) == 1:
        outputs = []
        for line in commands[0].splitlines():
            command = shlex.split(line)
            if command and command != ["set", "-e"]:
                outputs.append(execute(command))
        output = "\n".join(part for part in outputs if part)
        if state.get("disconnect_after_repair"):
            state["online"] = False
    else:
        output = execute(commands)
else:
    fail(f"Unexpected ADB command: {args!r}")

save()
if output:
    output += "\n"
    if state.get("crlf") and args[:1] == ["shell"]:
        output = output.replace("\n", "\r\n")
    sys.stdout.write(output)
'''


class FixWifiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fix-wifi-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake_adb = self.bin / "adb"
        fake_adb.write_text("#!/usr/bin/env python3\n" + FAKE_ADB)
        fake_adb.chmod(0o755)
        # Controller retries are driven by fixture state, not wall-clock delays.
        fake_sleep = self.bin / "sleep"
        fake_sleep.write_text("#!/bin/sh\nexit 0\n")
        fake_sleep.chmod(0o755)
        self.bash = shutil.which("bash")
        self.assertIsNotNone(self.bash)
        self.state_path = self.root / "state.json"
        self.state = {
            "serial": "watch-test",
            "online": True,
            "model": "Xiaomi Watch 2",
            "device": "axolotlaxie",
            "radio_enabled": True,
            "settings": {
                "global": {
                    MASTER: "1",
                    WIFI: "0",
                    "wifi_on": "1",
                    "wifi_scan_always_enabled": "0",
                    "adb_wifi_enabled": "1",
                },
                "system": {"clockwork_wifi_setting": "on", "bluetooth_preference": "off"},
            },
            "calls": [],
            "writes": [],
        }
        self.save_state()

    def save_state(self):
        self.state_path.write_text(json.dumps(self.state))

    def read_state(self):
        return json.loads(self.state_path.read_text())

    def run_fix(self, *args, input_text="", extra_env=None):
        env = os.environ.copy()
        env.pop("ANDROID_SERIAL", None)
        env.update({
            "PATH": str(self.bin) + os.pathsep + env["PATH"],
            "MOCK_ADB_STATE": str(self.state_path),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        env.update(extra_env or {})
        return subprocess.run(
            [self.bash, str(SCRIPT), *args],
            cwd=self.root,
            env=env,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def assert_no_writes(self):
        self.assertEqual(self.read_state()["writes"], [])

    def assert_overrides_clear(self):
        actual = self.read_state()
        self.assertEqual(actual["settings"]["global"][MASTER], "0")
        self.assertEqual(actual["settings"]["global"][WIFI], "0")
        self.assertEqual(actual["writes"], [["global", WIFI, "0"], ["global", MASTER, "0"]])

    def test_help_does_not_use_adb(self):
        result = self.run_fix("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Usage:", result.stdout)
        self.assertEqual(self.read_state()["calls"], [])

    def test_unknown_option_does_not_use_adb(self):
        result = self.run_fix("--unknown")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.read_state()["calls"], [])

    def test_missing_adb(self):
        empty_path = self.root / "empty-bin"
        empty_path.mkdir()
        result = self.run_fix("--yes", extra_env={"PATH": str(empty_path)})
        self.assertEqual(result.returncode, 1)
        self.assertIn("ADB is not installed", result.stderr)
        self.assert_no_writes()

    def test_no_connected_device(self):
        self.state["online"] = False
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 1)
        self.assert_no_writes()

    def test_multiple_devices_require_selection(self):
        self.state["multiple_devices"] = True
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ANDROID_SERIAL", result.stderr)
        self.assert_no_writes()

    def test_explicit_selection_pins_and_quotes_mdns_serial(self):
        serial = "watch-test (2)._adb-tls-connect._tcp"
        self.state.update(serial=serial, multiple_devices=True)
        self.save_state()
        result = self.run_fix("--yes", extra_env={"ANDROID_SERIAL": serial})
        self.assertEqual(result.returncode, 0, result.stderr)
        for call in self.read_state()["calls"][1:]:
            self.assertEqual(call["serial"], serial)
        rollback = [shlex.split(line) for line in result.stdout.splitlines() if line.startswith("  adb ")]
        self.assertEqual(rollback[0], ["adb", "-s", serial, "shell", "settings", "put", "global", MASTER, "1"])

    def test_rejects_other_devices_even_with_yes(self):
        self.state.update(device="other-device", model="Other Android device")
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("only supported", result.stderr)
        self.assert_no_writes()

    def test_dry_run_preserves_every_setting(self):
        original = copy.deepcopy(self.state["settings"])
        result = self.run_fix("--dry-run", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Dry run only; no changes were made", result.stdout)
        self.assertIn("Rollback commands", result.stdout)
        self.assertEqual(self.read_state()["settings"], original)
        self.assert_no_writes()

    def test_confirmation_rejects_other_text(self):
        result = self.run_fix(input_text="APPLY\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cancelled", result.stdout)
        self.assert_no_writes()

    def test_confirmation_handles_eof(self):
        result = self.run_fix()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cancelled", result.stdout)
        self.assert_no_writes()

    def test_interactive_fix_and_rollback_output_before_writes(self):
        result = self.run_fix(input_text="FIX\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_overrides_clear()
        self.assertLess(result.stdout.index("Rollback commands"), result.stdout.index("Restoring normal"))

    def test_master_only_override_and_unrelated_settings_preserved(self):
        original = copy.deepcopy(self.state["settings"])
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_overrides_clear()
        expected = original
        expected["global"][MASTER] = "0"
        self.assertEqual(self.read_state()["settings"], expected)
        self.assertIn("Verified: native Wi-Fi mediation is enabled", result.stdout)
        self.assertNotIn("test-network", result.stdout)

    def test_wifi_specific_override(self):
        self.state["settings"]["global"].update({MASTER: "0", WIFI: "1"})
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_overrides_clear()

    def test_both_overrides_use_one_remote_shell_master_last(self):
        self.state["settings"]["global"][WIFI] = "1"
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_overrides_clear()
        remote_writes = [call for call in self.read_state()["calls"] if (
            call["args"][:1] == ["shell"] and "settings put" in " ".join(call["args"])
        )]
        self.assertEqual(len(remote_writes), 1)

    def test_already_clear_is_a_read_only_noop(self):
        self.state["settings"]["global"][MASTER] = "0"
        self.save_state()
        result = self.run_fix()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No override is enabled", result.stdout)
        self.assert_no_writes()

    def test_second_run_is_idempotent(self):
        first = self.run_fix("--yes")
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_fix()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assert_overrides_clear()

    def test_unset_value_has_delete_rollback_not_literal_null(self):
        del self.state["settings"]["global"][WIFI]
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_overrides_clear()
        self.assertIn(f"shell settings delete global {WIFI}", result.stdout)
        self.assertNotIn(f"shell settings put global {WIFI} null", result.stdout)

    def test_both_unset_are_left_unset(self):
        del self.state["settings"]["global"][MASTER]
        del self.state["settings"]["global"][WIFI]
        self.save_state()
        result = self.run_fix()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_no_writes()
        self.assertNotIn(MASTER, self.read_state()["settings"]["global"])
        self.assertNotIn(WIFI, self.read_state()["settings"]["global"])

    def test_other_nonzero_integer_overrides_can_be_restored(self):
        self.state["settings"]["global"][MASTER] = "-1"
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_overrides_clear()
        self.assertIn(f"shell settings put global {MASTER} -1", result.stdout)

    def test_invalid_setting_value_blocks_writes(self):
        self.state["settings"]["global"][MASTER] = "not-an-integer"
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unexpected value", result.stderr)
        self.assert_no_writes()

    def test_setting_read_failure_blocks_writes(self):
        self.state["fail_read_key"] = WIFI
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 1)
        self.assert_no_writes()

    def test_unsupported_controller_blocks_writes(self):
        self.state["service_available"] = False
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unavailable", result.stderr)
        self.assert_no_writes()

    def test_failed_write_is_reported_without_auto_rollback(self):
        self.state["fail_put_key"] = MASTER
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("changes may be partial", result.stderr)
        self.assertEqual(self.read_state()["settings"]["global"][MASTER], "1")
        self.assertNotIn("Verified:", result.stdout)

    def test_silent_settings_failure_is_caught_by_readback(self):
        self.state["silent_put_failure"] = MASTER
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{MASTER} is still 1", result.stderr)
        self.assertNotIn("Verified:", result.stdout)

    def test_disconnected_after_repair_is_unverified_not_success(self):
        self.state["settings"]["system"]["clockwork_wifi_setting"] = "off"
        self.state["disconnect_after_repair"] = True
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 3)
        self.assertIn("Verification incomplete", result.stderr)
        self.assert_overrides_clear()
        self.assertFalse(self.read_state()["radio_enabled"])
        self.assertEqual(self.read_state()["settings"]["system"]["clockwork_wifi_setting"], "off")
        self.assertNotIn("Verified:", result.stdout)

    def test_disconnected_mid_write_is_unverified_not_success(self):
        self.state["disconnect_after_count"] = 1
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 3)
        self.assertIn("writes may be incomplete", result.stderr)
        self.assertEqual(self.read_state()["writes"], [["global", WIFI, "0"]])
        self.assertNotIn("Verified:", result.stdout)

    def test_disabled_radio_over_usb_is_a_valid_result(self):
        self.state["settings"]["system"]["clockwork_wifi_setting"] = "off"
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Wifi is disabled", result.stdout)
        self.assertEqual(self.read_state()["settings"]["system"]["clockwork_wifi_setting"], "off")

    def test_delayed_observer_retries_reads_without_repeating_writes(self):
        self.state["stale_reads"] = 1
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_overrides_clear()
        dumps = [call for call in self.read_state()["calls"] if call["args"] == (
            ["shell", "dumpsys", "WearConnectivityService"]
        )]
        self.assertEqual(len(dumps), 3)

    def test_stuck_controller_fails_after_bounded_checks(self):
        self.state["controller_stuck"] = True
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("controller still reports disabled", result.stderr)
        self.assert_overrides_clear()
        dumps = [call for call in self.read_state()["calls"] if call["args"] == (
            ["shell", "dumpsys", "WearConnectivityService"]
        )]
        self.assertEqual(len(dumps), 4)
        self.assertNotIn("Verified:", result.stdout)

    def test_unrelated_dump_section_cannot_disable_wifi_verification(self):
        self.state["unrelated_warning"] = True
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_overrides_clear()

    def test_controller_unavailable_after_write_is_unverified(self):
        self.state["service_lost_after_write"] = True
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 3)
        self.assert_overrides_clear()
        self.assertNotIn("Verified:", result.stdout)

    def test_setting_read_failure_after_write_is_unverified(self):
        self.state.update(fail_read_key=MASTER, read_failure_after_write=True)
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 3)
        self.assert_overrides_clear()
        self.assertNotIn("Verified:", result.stdout)

    def test_unknown_radio_status_is_unverified(self):
        self.state["radio_status"] = "Wi-Fi status unavailable"
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 3)
        self.assertIn("status format is unsupported", result.stderr)
        self.assertNotIn("Verified:", result.stdout)

    def test_remote_crlf_is_supported(self):
        self.state["crlf"] = True
        self.save_state()
        result = self.run_fix("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_overrides_clear()


if __name__ == "__main__":
    unittest.main()
