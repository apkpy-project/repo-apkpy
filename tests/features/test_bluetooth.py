# -*- coding: utf-8 -*-
"""Classic Bluetooth serial, and the permissions it deliberately does not ask for."""

import unittest

from apkpy_lib.core.features import bluetooth as codegen
from apkpy_lib.core.compiler import translate_python_to_android

B = chr(92)

PACKAGE = "com.apkpy.app"


def _runtime():
    """Everything generated for this feature, screen side and shared."""
    return (codegen.activity_runtime_java(PACKAGE)
            + codegen.shared_class_java(PACKAGE))
          # a backslash, so expected Java escapes read plainly


APP = '''from apkpy_lib import Screen, bluetooth, button, label, list_view, run, toast
home = Screen(id="home")
label("Serial", id="t", screen=home)
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
        bluetooth.send("LED ON")
    else:
        toast(reason)


def scan():
    bluetooth.devices(on_result=listed)


def link():
    bluetooth.connect("AA:BB:CC:DD:EE:FF", on_result=linked, on_line=incoming)


def drop():
    bluetooth.disconnect()


button("Scan", id="b1", screen=home, command=scan)
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
    return [l for l in java.splitlines()
            if marker in l and "private " not in l]


class TheVocabularyIsSharedTests(unittest.TestCase):

    def test_the_previewer_imports_the_compiler_table(self):
        from apkpy_lib.features import bluetooth as preview
        self.assertIs(preview.REASONS, codegen.REASONS)
        self.assertIs(preview.bluetooth.reasons, codegen.REASONS)

    def test_every_reason_the_java_can_report_is_in_the_table(self):
        runtime = _runtime()
        import re
        reported = set(re.findall(r'onResult\((?:false|true), "([a-z_]+)"\)', runtime))
        reported |= set(re.findall(r'return "([a-z_]+)";', runtime))
        self.assertTrue(reported)
        for word in reported:
            self.assertIn(word, codegen.REASONS, word)

    def test_a_reason_is_never_empty(self):
        for reason in codegen.REASONS:
            self.assertTrue(reason.strip(), reason)


class ThePermissionsTests(unittest.TestCase):
    """The whole point of listing paired devices instead of scanning."""

    def test_it_never_asks_for_location(self):
        # A scan would have needed ACCESS_FINE_LOCATION. An app that only talks
        # to a printer must not ask where its user is.
        self.assertNotIn("ACCESS_FINE_LOCATION", _manifest(APP))

    def test_the_legacy_permission_stops_at_api_30(self):
        manifest = _manifest(APP)
        self.assertIn(
            '<uses-permission android:name="android.permission.BLUETOOTH"'
            ' android:maxSdkVersion="30" />', manifest)

    def test_the_modern_permission_is_uncapped(self):
        self.assertIn(
            '<uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />',
            _manifest(APP))

    def test_the_attributes_never_reach_a_java_identifier(self):
        """javac stopped on PERMISSION_REQ_BLUETOOTH|maxSdkVersion=30.

        The manifest carries attributes in the permission string; everything
        that builds a Java symbol from it has to see the bare name. Brace
        counting does not catch this -- only a real build did.
        """
        java = _java(APP)
        self.assertIn("private static final int PERMISSION_REQ_BLUETOOTH = ", java)
        self.assertNotIn("|", "".join(
            l for l in java.splitlines() if "PERMISSION_REQ" in l))

    def test_a_permission_callback_switch_uses_the_bare_name(self):
        from apkpy_lib.core.compiler import _permission_symbol
        self.assertEqual(_permission_symbol("BLUETOOTH|maxSdkVersion=30"),
                         "BLUETOOTH")
        self.assertEqual(_permission_symbol("CAMERA"), "CAMERA")

    def test_a_plain_permission_still_writes_the_old_way(self):
        # The attribute syntax must not change the XML for every other app.
        from apkpy_lib.core.compiler import _generate_manifest
        manifest = _generate_manifest(["home"], "home",
                                      declared_permissions=["INTERNET"])
        self.assertIn(
            '<uses-permission android:name="android.permission.INTERNET" />',
            manifest)


class TheGeneratedAppTests(unittest.TestCase):

    def test_all_four_verbs_reach_the_activity(self):
        java = _java(APP)
        for marker in ("_btPairedDevices(", "_btConnect(", "_btSend(",
                       "_btDisconnect()"):
            self.assertTrue(_calls(java, marker), marker)

    def test_it_survives_a_lambda_that_calls_a_helper(self):
        """The Activity has TWO command dispatchers, and both must be wired.

        Wiring only the first is how the biometrics work shipped a button that
        silently did nothing.
        """
        source = APP.replace("command=scan)", "command=lambda: scan())")
        self.assertTrue(_calls(_java(source), "_btPairedDevices("))

    def test_the_line_callback_is_passed_separately_from_the_result(self):
        java = _java(APP)
        connect = [l for l in java.splitlines() if "_btConnect(" in l
                   and "private void" not in l][0]
        self.assertIn("pythonCallback_linked", connect)
        self.assertIn("pythonCallback_incoming", connect)

    def test_the_socket_work_happens_off_the_ui_thread(self):
        runtime = _runtime()
        # connect() blocks; doing it inline would freeze the app and trip
        # Android's StrictMode.
        self.assertIn("new Thread(", runtime)
        self.assertIn("MAIN.post(", runtime)

    def test_a_sent_line_ends_with_whatever_the_call_chose(self):
        # It used to hardcode a newline. The terminator is an argument now,
        # because hardware that wants a carriage return answers nothing
        # without one.
        self.assertIn(chr(40) + "text + terminator).getBytes",
                      _runtime())

    def test_the_adapter_is_checked_before_any_socket(self):
        runtime = _runtime()
        self.assertLess(runtime.index("blockedReason"),
                        runtime.index("createRfcommSocketToServiceRecord"))

    def test_an_app_that_never_asks_carries_none_of_it(self):
        java = _java(APP_WITHOUT)
        self.assertNotIn("BluetoothResultCallback", java)
        self.assertNotIn("android.bluetooth", java)
        self.assertNotIn("BLUETOOTH", _manifest(APP_WITHOUT))

    def test_the_java_is_balanced(self):
        java = _java(APP)
        for opener, closer in (("{", "}"), ("(", ")")):
            self.assertEqual(java.count(opener), java.count(closer))


class TheThreeGapsClosedTests(unittest.TestCase):
    """The three things that stood between "it compiles" and "it works"."""

    def test_it_asks_for_the_permission_instead_of_only_declaring_it(self):
        """Without this the feature is dead on every Android 12 phone.

        BLUETOOTH_CONNECT became a runtime permission: an app that only names
        it in the manifest is refused forever, and the person is never offered
        the choice. checkSelfPermission just keeps saying no.
        """
        runtime = _runtime()
        self.assertIn("RequestMultiplePermissions", runtime)
        self.assertIn("_btPermissionLauncher.launch(", runtime)
        self.assertIn("BLUETOOTH_CONNECT", runtime)

    def test_it_only_asks_once(self):
        # Re-asking on every tap after a refusal is how an app gets uninstalled.
        runtime = _runtime()
        self.assertIn("if (_btAsked) return true;", runtime)

    def test_every_verb_goes_through_the_permission_gate(self):
        runtime = _runtime()
        for method in ("_btPairedDevices", "_btConnect"):
            start = runtime.index("private void %s(" % method)
            self.assertIn("_btReady(", runtime[start:start + 400], method)

    def test_the_screen_drops_its_callback_but_not_the_link(self):
        # Closing here is what used to end the conversation on navigation.
        java = _java(APP)
        destroy = java.index("protected void onDestroy")
        window = java[destroy:destroy + 400]
        self.assertIn("_btReleaseListener();", window)
        self.assertNotIn("_btDisconnect();", window)

    def test_the_terminator_can_be_chosen(self):
        source = APP.replace('bluetooth.send("LED ON")',
                             'bluetooth.send("ATZ", terminator="return")')
        self.assertIn('_btSend("ATZ", "%sr",' % (B,), _java(source))

    def test_the_default_terminator_is_a_newline(self):
        self.assertIn('_btSend("LED ON", "%sn",' % (B,), _java(APP))

    def test_a_carriage_return_survives_the_escaper(self):
        # It used to be stripped, which would have silently dropped the very
        # terminator this exists to support.
        self.assertEqual(codegen._java_string(chr(13)), '"%sr"' % (B,))

    def test_the_names_and_the_characters_mean_the_same(self):
        self.assertEqual(codegen.normalise_terminator("return"), chr(13))
        self.assertEqual(codegen.normalise_terminator(chr(13)), chr(13))
        self.assertEqual(codegen.normalise_terminator("none"), "")
        self.assertEqual(codegen.normalise_terminator(None), chr(10))

    def test_the_previewer_takes_the_same_argument(self):
        from apkpy_lib.features import bluetooth as preview
        seen = []
        preview.bluetooth.send("ATZ", terminator="return",
                               on_result=lambda ok, v: seen.append(ok))
        self.assertEqual(seen, [False])   # nothing connected, but it accepted it


class TheEnablePromptTests(unittest.TestCase):

    def test_it_offers_to_turn_bluetooth_on(self):
        runtime = _runtime()
        self.assertIn("ACTION_REQUEST_ENABLE", runtime)
        self.assertIn("_btEnableLauncher.launch(", runtime)

    def test_it_asks_for_permission_first(self):
        runtime = codegen.activity_runtime_java(PACKAGE)
        ready = runtime[runtime.index("private boolean _btReady"):]
        ready = ready[:ready.index("private void _btPairedDevices")]
        self.assertLess(ready.index("_btPermissionLauncher"),
                        ready.index("ACTION_REQUEST_ENABLE"))

    def test_it_only_offers_once(self):
        self.assertIn("if (_btAskedEnable) return true;",
                      _runtime())



class TheLinkBelongsToOneScreenTests(unittest.TestCase):
    """A limitation worth a test, so nobody assumes otherwise later."""

    def test_the_link_does_not_live_on_a_screen(self):
        """It used to, and that ended the conversation on every navigation.

        A field on an Activity dies with it, and a static would not help --
        each screen is a different class, so each would get its own copy. The
        socket lives in one shared class instead.
        """
        source = APP.replace(
            'home = Screen(id="home")',
            'home = Screen(id="home")' + chr(10) + 'other = Screen(id="other")'
        ).replace(
            'button("Drop", id="b3", screen=home, command=drop)',
            'button("Drop", id="b3", screen=home, command=drop)' + chr(10)
            + 'label("x", id="o", screen=other)')
        files = translate_python_to_android(source)
        self.assertIn("java/ApkpyBluetooth.java", files)
        activities = [b for n, b in files.items()
                      if n.endswith(".java") and "Activity" in n]
        self.assertEqual(len(activities), 2)
        for body in activities:
            self.assertNotIn("private java.io.OutputStream", body)
            self.assertIn("ApkpyBluetooth.send(", body)

    def test_reconnecting_to_the_same_device_adopts_the_new_listener(self):
        # How a link survives a navigation: the next screen calls connect()
        # again and inherits the open conversation instead of reopening it.
        shared = codegen.shared_class_java(PACKAGE)
        self.assertIn("if (isConnected() && sAddress.equalsIgnoreCase(address))",
                      shared)

class TheThreadingReviewTests(unittest.TestCase):
    """Found by reading, not by compiling."""

    def test_a_disconnect_we_caused_is_not_announced_as_a_loss(self):
        # Closing the socket wakes the reader, which used to report "lost" --
        # so disconnect() told the app its link had died, and connecting
        # elsewhere told the NEW screen the same thing.
        shared = codegen.shared_class_java(PACKAGE)
        self.assertIn("final int mine = sGeneration;", shared)
        self.assertIn("if (mine == sGeneration) post(sLine, false", shared)

    def test_disconnecting_moves_the_generation_on(self):
        shared = codegen.shared_class_java(PACKAGE)
        close = shared[shared.index("public static void disconnect()"):]
        self.assertIn("sGeneration++;", close[:200])

    def test_state_that_crosses_threads_is_volatile(self):
        # Written on the connect thread, read on the main one.
        shared = codegen.shared_class_java(PACKAGE)
        for field in ("sSocket", "sOut", "sAddress", "sGeneration"):
            self.assertIn("volatile", [l for l in shared.splitlines()
                                       if (" " + field + ";") in l
                                       or (" " + field + " =") in l][0], field)



class ThePreviewerTests(unittest.TestCase):

    def test_it_never_constructs_a_window(self):
        from apkpy_lib import ui
        from apkpy_lib.features import bluetooth as preview
        if ui._app._instance is not None:
            self.skipTest("a Previewer window already exists in this process")
        preview.bluetooth.devices(on_result=lambda *_: None)
        preview.bluetooth.connect("00:00:00:00:00:01", on_result=lambda *_: None)
        self.assertIsNone(ui._app._instance)

    def test_the_simulated_device_is_named_as_one(self):
        from apkpy_lib.features import bluetooth as preview
        seen = []
        preview.bluetooth.devices(on_result=lambda ok, v: seen.append((ok, v)))
        self.assertTrue(seen[0][0])
        self.assertIn("Simulated", seen[0][1])

    def test_the_device_list_is_json_set_items_can_read(self):
        import json
        from apkpy_lib.features import bluetooth as preview
        seen = []
        preview.bluetooth.devices(on_result=lambda ok, v: seen.append(v))
        rows = json.loads(seen[0])
        self.assertEqual(sorted(rows[0]), ["address", "name"])

    def test_sending_with_nothing_connected_says_so(self):
        from apkpy_lib.features import bluetooth as preview
        seen = []
        preview.bluetooth.send("x", on_result=lambda ok, v: seen.append((ok, v)))
        self.assertEqual(seen, [(False, "not_connected")])


class TheIconsTests(unittest.TestCase):

    def test_the_catalogue_has_the_radio_and_the_link(self):
        from apkpy_lib import icons
        for name in ("bluetooth", "link"):
            self.assertIsNotNone(icons.resolve(name), name)
            self.assertNotEqual(icons.resolve(name), icons.resolve("circle"), name)

    def test_both_backends_draw_the_same_glyph(self):
        from apkpy_lib import icons
        from apkpy_lib.core.compiler import _material_icon_path
        for name in ("bluetooth", "link"):
            self.assertEqual(_material_icon_path(name), icons.resolve(name), name)


if __name__ == "__main__":
    unittest.main()
