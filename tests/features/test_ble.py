# -*- coding: utf-8 -*-
"""Bluetooth Low Energy: the UART default, the UUIDs, and the scan's cost."""

import unittest

from apkpy_lib.core.features import ble as codegen
from apkpy_lib.core.compiler import translate_python_to_android

B = chr(92)

PACKAGE = "com.apkpy.app"


def _runtime():
    """Everything generated for this feature, screen side and shared."""
    return (codegen.activity_runtime_java(PACKAGE)
            + codegen.shared_class_java(PACKAGE))



APP = '''from apkpy_lib import Screen, ble, button, label, list_view, run, toast
home = Screen(id="home")
found = list_view([], id="found", screen=home)
log = label("", id="log", screen=home)


def listed(ok, devices):
    if ok:
        found.set_items(devices, title="name", subtitle="address")
    else:
        toast(devices)


def incoming(ok, line):
    if ok:
        log.set_value(line)
    else:
        toast("lost")


def linked(ok, reason):
    if ok:
        ble.send("LED ON")
    else:
        toast(reason)


def look():
    ble.scan(on_result=listed, seconds=6)


def link():
    ble.connect("AA:BB:CC:DD:EE:01", on_result=linked, on_line=incoming)


def drop():
    ble.disconnect()


button("Scan", id="b1", screen=home, command=look)
button("Link", id="b2", screen=home, command=link)
button("Drop", id="b3", screen=home, command=drop)
run(start_screen=home)
'''

APP_WITHOUT = '''from apkpy_lib import Screen, button, label, run, toast
home = Screen(id="home")
label("plain", id="t", screen=home)
button("Tap", id="go", screen=home, command=lambda: toast("hi"))
run(start_screen=home)
'''


def _java(source):
    files = translate_python_to_android(source)
    return "\n".join(b for n, b in files.items() if n.endswith(".java"))


def _manifest(source):
    return translate_python_to_android(source).get("AndroidManifest.xml", "")


def _calls(java, marker):
    return [l for l in java.splitlines() if marker in l and "private " not in l]


class TheUuidsTests(unittest.TestCase):

    def test_a_16_bit_shorthand_expands(self):
        self.assertEqual(codegen.expand_uuid("180d"),
                         "0000180d-0000-1000-8000-00805f9b34fb")

    def test_a_full_uuid_is_left_alone_but_lowercased(self):
        self.assertEqual(
            codegen.expand_uuid("6E400001-B5A3-F393-E0A9-E50E24DCCA9E"),
            codegen.UART["service"])

    def test_nothing_falls_back_to_the_default(self):
        self.assertEqual(codegen.expand_uuid("", codegen.UART["write"]),
                         codegen.UART["write"])
        self.assertEqual(codegen.expand_uuid(None, "x"), "x")

    def test_the_previewer_expands_them_the_same_way(self):
        from apkpy_lib.features import ble as preview
        self.assertIs(preview.UART, codegen.UART)


class TheDefaultProfileTests(unittest.TestCase):

    def test_a_connect_with_no_uuids_uses_nordic_uart(self):
        java = _java(APP)
        connect = _calls(java, "_bleConnect(")[0]
        for uuid in codegen.UART.values():
            self.assertIn(uuid, connect)

    def test_named_uuids_replace_the_default(self):
        source = APP.replace(
            'ble.connect("AA:BB:CC:DD:EE:01", on_result=linked, on_line=incoming)',
            'ble.connect("AA:BB:CC:DD:EE:01", service="180d",'
            ' notify_uuid="2a37", on_result=linked)')
        connect = _calls(_java(source), "_bleConnect(")[0]
        self.assertIn("0000180d-0000-1000-8000-00805f9b34fb", connect)
        self.assertIn("00002a37-0000-1000-8000-00805f9b34fb", connect)


class ThePermissionsTests(unittest.TestCase):
    """A scan costs a permission. It is declared as narrowly as it can be."""

    def test_the_location_grant_stops_at_api_30(self):
        # BLE really does have to scan, so unlike classic serial this cannot be
        # avoided -- but a modern install must never see a location request.
        self.assertIn(
            '<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"'
            ' android:maxSdkVersion="30" />', _manifest(APP))

    def test_the_scan_declares_it_is_not_for_location(self):
        self.assertIn(
            '<uses-permission android:name="android.permission.BLUETOOTH_SCAN"'
            ' android:usesPermissionFlags="neverForLocation" />', _manifest(APP))

    def test_the_attributes_never_reach_a_java_identifier(self):
        # The bug a real build caught on the classic module.
        java = _java(APP)
        self.assertNotIn("|", "".join(
            l for l in java.splitlines() if "PERMISSION_REQ" in l))


class TheGeneratedAppTests(unittest.TestCase):

    def test_all_four_verbs_reach_the_activity(self):
        java = _java(APP)
        for marker in ("_bleScan(", "_bleConnect(", "_bleSend(",
                       "_bleDisconnect()"):
            self.assertTrue(_calls(java, marker), marker)

    def test_it_survives_a_lambda_that_calls_a_helper(self):
        source = APP.replace("command=look)", "command=lambda: look())")
        self.assertTrue(_calls(_java(source), "_bleScan("))

    def test_the_notification_descriptor_is_written(self):
        # setCharacteristicNotification alone only sets a local flag; without
        # the CCCD write the device never sends anything and the app looks dead.
        runtime = _runtime()
        self.assertIn("ENABLE_NOTIFICATION_VALUE", runtime)
        self.assertIn("writeDescriptor", runtime)
        self.assertIn("00002902-0000-1000-8000-00805f9b34fb", runtime)

    def test_services_are_discovered_before_characteristics_are_used(self):
        runtime = _runtime()
        self.assertLess(runtime.index("discoverServices"),
                        runtime.index("getCharacteristic"))

    def test_gatt_callbacks_are_posted_to_the_ui_thread(self):
        # They arrive on a binder thread, and app code touches labels.
        self.assertIn("MAIN.post(", _runtime())

    def test_the_scan_is_stopped_before_connecting(self):
        # Scanning through a connect is the classic reason it never completes.
        shared = codegen.shared_class_java(PACKAGE)
        connect = shared.index("public static void connect(")
        self.assertIn("stopScan(app)", shared[connect:connect + 900])

    def test_the_seconds_are_clamped(self):
        source = APP.replace("seconds=6", "seconds=9999")
        self.assertIn("_bleScan(60,", _java(source))

    def test_an_app_that_never_asks_carries_none_of_it(self):
        java = _java(APP_WITHOUT)
        self.assertNotIn("BleResultCallback", java)
        self.assertNotIn("BluetoothGatt", java)
        self.assertNotIn("BLUETOOTH_SCAN", _manifest(APP_WITHOUT))

    def test_the_java_is_balanced(self):
        java = _java(APP)
        for opener, closer in (("{", "}"), ("(", ")")):
            self.assertEqual(java.count(opener), java.count(closer))


class TheThreeGapsClosedTests(unittest.TestCase):

    def test_it_asks_for_the_permissions_instead_of_only_declaring_them(self):
        # Without this, every Android 12 phone refuses forever and never
        # offers the person the choice.
        runtime = _runtime()
        self.assertIn("RequestMultiplePermissions", runtime)
        self.assertIn("_blePermissionLauncher.launch(", runtime)

    def test_it_asks_for_scan_and_connect_above_31_and_location_below(self):
        runtime = _runtime()
        missing = runtime[runtime.index("_bleMissingPermissions"):]
        missing = missing[:missing.index("private boolean _bleReady")]
        self.assertIn("BLUETOOTH_SCAN", missing)
        self.assertIn("BLUETOOTH_CONNECT", missing)
        self.assertIn("ACCESS_FINE_LOCATION", missing)

    def test_it_only_asks_once(self):
        self.assertIn("if (_bleAsked) return true;",
                      _runtime())

    def test_every_verb_goes_through_the_permission_gate(self):
        runtime = _runtime()
        for method in ("_bleScan", "_bleConnect"):
            start = runtime.index("private void %s(" % method)
            self.assertIn("_bleReady(", runtime[start:start + 500], method)

    def test_the_screen_drops_its_callback_but_not_the_link(self):
        java = _java(APP)
        destroy = java.index("protected void onDestroy")
        window = java[destroy:destroy + 400]
        self.assertIn("_bleReleaseListener();", window)
        self.assertNotIn("_bleDisconnect();", window)

    def test_the_terminator_can_be_chosen(self):
        source = APP.replace('ble.send("LED ON")',
                             'ble.send("ATZ", terminator="return")')
        self.assertIn('_bleSend("ATZ", "' + B + 'r",', _java(source))

    def test_the_default_terminator_is_a_newline(self):
        self.assertIn('_bleSend("LED ON", "' + B + 'n",', _java(APP))

    def test_a_carriage_return_survives_the_escaper(self):
        self.assertEqual(codegen._java_string(chr(13)), chr(34) + B + "r" + chr(34))

    def test_both_radios_share_one_terminator_table(self):
        from apkpy_lib.core.features import bluetooth as classic
        self.assertIs(codegen.TERMINATORS, classic.TERMINATORS)



class TheTwoRadiosCoexistTests(unittest.TestCase):

    def test_an_app_can_use_both_without_a_clash(self):
        source = APP.replace(
            "from apkpy_lib import Screen, ble, button",
            "from apkpy_lib import Screen, ble, bluetooth, button").replace(
            "def drop():\n    ble.disconnect()",
            "def drop():\n    ble.disconnect()\n    bluetooth.devices(on_result=listed)")
        java = _java(source)
        self.assertTrue(_calls(java, "_bleScan("))
        self.assertTrue(_calls(java, "_btPairedDevices("))
        self.assertIn("private interface BleResultCallback", java)
        self.assertIn("private interface BluetoothResultCallback", java)
        for opener, closer in (("{", "}"), ("(", ")")):
            self.assertEqual(java.count(opener), java.count(closer))


class TheDeadEndsRemovedTests(unittest.TestCase):
    """Three ways the app used to look broken when it was not."""

    def test_it_offers_to_turn_bluetooth_on(self):
        # Reporting "off" and stopping left the person to find Settings alone.
        runtime = _runtime()
        self.assertIn("ACTION_REQUEST_ENABLE", runtime)
        self.assertIn("_bleEnableLauncher.launch(", runtime)

    def test_it_asks_for_permission_before_asking_to_enable(self):
        # The enable prompt itself needs BLUETOOTH_CONNECT on API 31+.
        runtime = _runtime()
        ready = runtime[runtime.index("private boolean _bleReady"):]
        ready = ready[:ready.index("private void _bleScan")]
        self.assertLess(ready.index("_blePermissionLauncher"),
                        ready.index("ACTION_REQUEST_ENABLE"))

    def test_it_only_offers_once(self):
        self.assertIn("if (_bleAskedEnable) return true;",
                      _runtime())

    def test_writes_are_queued_rather_than_refused(self):
        # GATT allows one outstanding operation; a second send() during the
        # first used to come back "failed", which reads as flaky hardware.
        shared = codegen.shared_class_java(PACKAGE)
        self.assertIn("QUEUE", shared)
        self.assertIn("private static void pump()", shared)
        self.assertIn("onCharacteristicWrite", shared)

    def test_the_queue_is_emptied_when_the_link_closes(self):
        runtime = _runtime()
        close = runtime.index("public static void disconnect")
        self.assertIn("QUEUE.clear();", runtime[close:close + 400])

    def test_a_connect_that_never_answers_times_out(self):
        # connectGatt to a device that is not there never calls back, so the
        # app waited forever instead of hearing "unreachable".
        runtime = _runtime()
        self.assertIn("sSettled", runtime)
        self.assertIn("15000L", runtime)
        timeout = runtime[runtime.index("postDelayed", runtime.index("sSettled = false")):]
        self.assertIn('"unreachable"', timeout[:600])

    def test_a_verdict_disarms_the_timeout(self):
        # Otherwise a connected device is torn down 15 seconds later.
        runtime = _runtime()
        self.assertIn("sSettled = true;", runtime)
        self.assertGreaterEqual(runtime.count("sSettled = true;"), 3)



class TheThreadingReviewTests(unittest.TestCase):
    """Found by reading, not by compiling."""

    def test_a_dropped_link_closes_the_gatt_client(self):
        # Android allows a limited number of GATT clients per app. Leaking one
        # per drop eventually breaks BLE everywhere in the app.
        shared = codegen.shared_class_java(PACKAGE)
        drop = shared[shared.index("STATE_DISCONNECTED"):]
        self.assertIn("gatt.close()", drop[:900])

    def test_a_stale_timeout_cannot_kill_a_newer_connection(self):
        shared = codegen.shared_class_java(PACKAGE)
        self.assertIn("mine != sGeneration", shared)

    def test_gatt_state_that_crosses_threads_is_volatile(self):
        shared = codegen.shared_class_java(PACKAGE)
        for field in ("sGatt", "sWrite", "sLine", "sSettled", "sWriting"):
            matches = [l for l in shared.splitlines()
                       if (" " + field + ";") in l or (" " + field + " =") in l]
            self.assertIn("volatile", matches[0], field)



class ThePreviewerTests(unittest.TestCase):

    def test_it_never_constructs_a_window(self):
        from apkpy_lib import ui
        from apkpy_lib.features import ble as preview
        if ui._app._instance is not None:
            self.skipTest("a Previewer window already exists in this process")
        preview.ble.scan(on_result=lambda *_: None)
        preview.ble.connect("00:00:00:00:00:02", on_result=lambda *_: None)
        self.assertIsNone(ui._app._instance)

    def test_the_simulated_device_is_named_as_one(self):
        from apkpy_lib.features import ble as preview
        seen = []
        preview.ble.scan(on_result=lambda ok, v: seen.append(v))
        self.assertIn("Simulated", seen[0])

    def test_the_scan_result_is_json_set_items_can_read(self):
        import json
        from apkpy_lib.features import ble as preview
        seen = []
        preview.ble.scan(on_result=lambda ok, v: seen.append(v))
        rows = json.loads(seen[0])
        self.assertEqual(sorted(rows[0]), ["address", "name"])

    def test_each_radio_labels_the_monitor_as_itself(self):
        """They share one panel, so each must pass its own name to it.

        Storing the label in the shared state instead left a serial link
        showing "BLE MONITOR" after a BLE session.
        """
        from apkpy_lib.features import ble as preview_ble
        from apkpy_lib.features import bluetooth as preview_spp

        labels = []
        real_window, real_panel = preview_spp._window, preview_spp._open_panel
        preview_spp._window = lambda: ("ui", "app")
        preview_spp._open_panel = lambda ui, app, transport="SERIAL": labels.append(transport)
        try:
            preview_spp._connect(preview_spp.SIMULATED_ADDRESS, None, None)
            preview_spp._state["connected"] = False
            preview_ble._connect(preview_ble.SIMULATED_ADDRESS, None, None)
        finally:
            preview_spp._window, preview_spp._open_panel = real_window, real_panel
            preview_spp._state["connected"] = False
            preview_spp._state["panel"] = None
            preview_spp._state["log"] = None
        self.assertEqual(labels, ["SERIAL", "BLE"])

    def test_the_reasons_are_the_compiler_table(self):
        from apkpy_lib.features import ble as preview
        self.assertIs(preview.REASONS, codegen.REASONS)


if __name__ == "__main__":
    unittest.main()
