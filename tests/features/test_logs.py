# -*- coding: utf-8 -*-
"""apkpy logs: what the app prints on the phone, out of all that logcat holds.

print() in the app is android.util.Log.i("apkpy", ...) on the phone, among the
lines of every other app and of Android. `apkpy logs` keeps the app's own:
found by its package, followed through a crash and a reopen. These tests feed
lines as `adb logcat -v threadtime` writes them; no phone is needed.
"""

import io
import unittest
from unittest import mock

from click.testing import CliRunner

from apkpy_lib import logs as applogs
from apkpy_lib.cli import main

PKG = "com.example.notes"


def at(pid, level, tag, msg, tid=None):
    return "10-29 18:43:01.120  %5s  %5s %s %-8s: %s\n" % (pid, tid or pid, level, tag, msg)


START = at(1534, "I", "ActivityManager",
           "Start proc 4321:com.example.notes/u0a234 for next-top-activity "
           "{com.example.notes/com.example.notes.Screen_homeActivity}")
DIED = at(1534, "I", "ActivityManager", "Process com.example.notes (pid 4321) has died: fg  TOP")
CRASH = [at(4321, "E", "AndroidRuntime", m) for m in (
    "FATAL EXCEPTION: main",
    "Process: com.example.notes, PID: 4321",
    "TypeError: '<' not supported between instances of 'int' and 'str'",
    "\tat com.example.notes.Screen_homeActivity._apkpyCmp(Screen_homeActivity.java:445)",
    "\tat java.util.TimSort.sort(TimSort.java:220)",
    "\tat android.view.View.performClick(View.java:7448)",
    "\tat com.example.notes.Screen_homeActivity$3.onClick(Screen_homeActivity.java:812)",
    "Caused by: java.lang.NumberFormatException: For input string: \"x\"",
    "\t... 12 more",
)]


def shown(follower, lines):
    out = []
    for line in lines:
        out.extend(follower.feed(line))
    return out


class WhatIsKept(unittest.TestCase):

    def test_print_is_shown_as_it_was_printed(self):
        f = applogs.Follower(PKG)
        self.assertEqual(shown(f, [START, at(4321, "I", "apkpy", "total: 12 items")]),
                         ["-- com.example.notes started (pid 4321) --", "total: 12 items"])

    def test_other_apps_and_android_noise_are_left_out(self):
        f = applogs.Follower(PKG)
        f.pids.add("4321")
        self.assertEqual(shown(f, [
            at(999, "I", "apkpy", "another ApkPy app"),
            at(4321, "D", "OpenGLRenderer", "Davey! duration=712ms"),
            at(4321, "W", "System", "A resource failed to call close."),
            at(1534, "E", "ActivityManager", "ANR in com.other.app"),
            "--------- beginning of main\n",
        ]), [])

    def test_apkpys_warnings_and_errors_keep_their_level_and_tag(self):
        f = applogs.Follower(PKG)
        f.pids.add("4321")
        self.assertEqual(shown(f, [
            at(4321, "W", "apkpy", "the photo could not be read"),
            at(4321, "E", "ApkpyData", "database is locked"),
            at(4321, "W", "ApkPy", "the widget could not be updated"),
            at(4321, "W", "ApkpyContacts", "no permission"),
        ]), ["W/apkpy: the photo could not be read",
             "E/ApkpyData: database is locked",
             "W/ApkPy: the widget could not be updated",
             "W/ApkpyContacts: no permission"])

    def test_androids_own_errors_in_the_apps_process_are_left_out(self):
        # What a Xiaomi (HyperOS) wrote in the process of a test app, at
        # level E, on each start: none of it was the app's.
        f = applogs.Follower(PKG)
        f.pids.add("4321")
        self.assertEqual(shown(f, [
            at(4321, "E", "Zygote", "process_name_ptr:4321 com.example.notes"),
            at(4321, "E", "MiuiPreloadClassImpl", "invoke error."),
            at(4321, "E", "ashmem", "Pinning is deprecated since Android Q."),
            at(4321, "E", "TurboSchedMonitor", "failed to find setSchedAffinity method"),
            at(4321, "E", "HWUI", "Archi_PipelineCache, LoadPipelineInfoFile failed"),
            at(4321, "E", "MI-PreRender", "init cloud whiteList failed"),
            at(4321, "E", "ple.notes", "[perfctl] 4321 4321 FPSGO ver:7"),
            at(4321, "E", "LB", "fail to open file: No such file or directory"),
            at(4321, "E", "MediaPlayer", "error (1, -2147483648)"),
        ]), [])

    def test_a_caught_errors_trace_shows_the_apps_lines(self):
        f = applogs.Follower(PKG)
        f.pids.add("4321")
        self.assertEqual(shown(f, [
            at(4321, "W", "System.err", "android.database.sqlite.SQLiteException: no such table: notes"),
            at(4321, "W", "System.err", "\tat android.database.sqlite.SQLiteConnection.nativePrepareStatement(Native Method)"),
            at(4321, "W", "System.err", "\tat com.example.notes.Screen_homeActivity.save(Screen_homeActivity.java:301)"),
            at(4321, "W", "System.err", "\t... 12 more"),
        ]), ["W/System.err: android.database.sqlite.SQLiteException: no such table: notes",
             "W/System.err: \tat com.example.notes.Screen_homeActivity.save(Screen_homeActivity.java:301)"])

    def test_all_shows_androids_own_errors_too(self):
        f = applogs.Follower(PKG, everything=True)
        f.pids.add("4321")
        self.assertEqual(shown(f, [at(4321, "E", "Zygote", "process_name_ptr:4321")]),
                         ["E/Zygote: process_name_ptr:4321"])

    def test_all_shows_every_line_of_the_app_and_still_no_other(self):
        f = applogs.Follower(PKG, everything=True)
        f.pids.add("4321")
        self.assertEqual(shown(f, [at(4321, "D", "OpenGLRenderer", "Davey!"),
                                   at(999, "D", "OpenGLRenderer", "not ours")]),
                         ["D/OpenGLRenderer: Davey!"])

    def test_a_crash_shows_the_error_and_the_apps_own_lines(self):
        f = applogs.Follower(PKG)
        f.pids.add("4321")
        self.assertEqual(shown(f, CRASH + [DIED]), [
            "",
            "The app stopped with an error:",
            "  TypeError: '<' not supported between instances of 'int' and 'str'",
            "    at com.example.notes.Screen_homeActivity._apkpyCmp(Screen_homeActivity.java:445)",
            "    at com.example.notes.Screen_homeActivity$3.onClick(Screen_homeActivity.java:812)",
            "  Caused by: java.lang.NumberFormatException: For input string: \"x\"",
            "-- com.example.notes stopped --",
        ])


APP = '''from apkpy_lib import *
home = Screen(id="home")
field = inputs("x", id="field", screen=home)
out = label("", id="out", screen=home)


def add(a, b):
    total = a + b
    return total


def go():
    n = int(field.get_value())
    if n > 3:
        out.set_value("big")
    else:
        out.set_value(str(add(n, 1)))


button("Go", id="b1", command=go, screen=home)
run(start_screen=home)
'''


def _built(source=APP):
    import json
    from apkpy_lib.core.compiler import translate_python_to_android
    files = translate_python_to_android(source)
    assert "error.txt" not in files, files.get("error.txt")
    return files, json.loads(files["apkpy/lines.json"])


def _java_line(java, piece, after=0):
    """The 1-based line of the generated Java holding *piece*."""
    for number, text in enumerate(java.split("\n"), 1):
        if number > after and piece in text:
            return number
    raise AssertionError(piece)


class TheCrashNamesThePythonLine(unittest.TestCase):
    """A crash names lines of the Java; the build's map gives the Python."""

    def test_the_java_has_no_marks_left_and_the_map_names_each_line(self):
        files, lines = _built()
        self.assertFalse([k for k, v in files.items() if isinstance(v, str) and "\x00" in v])
        java = files["java/Screen_homeActivity.java"]
        click = _java_line(java, "public void onClick(")
        for piece, line, text in (
                ("ApkpyValues.toInt(", 13, "n = int(field.get_value())"),
                ("> 3) {", 14, "if n > 3:"),
                ('setText(String.valueOf("big"))', 15, 'out.set_value("big")'),
                ("} else {", 14, "if n > 3:"),
                ("pythonCallback_add(", 17, "out.set_value(str(add(n, 1)))")):
            self.assertEqual(
                applogs.python_line(lines, "Screen_homeActivity.java",
                                    _java_line(java, piece, after=click)),
                ("writehere.py", line, text), piece)
        self.assertEqual(applogs.python_line(lines, "Screen_homeActivity.java",
                                             _java_line(java, "String total =")),
                         ("writehere.py", 8, "total = a + b"))

    def test_apkpys_own_java_has_no_python_line(self):
        files, lines = _built()
        java = files["java/Screen_homeActivity.java"]
        self.assertIsNone(applogs.python_line(
            lines, "Screen_homeActivity.java", _java_line(java, "private long _apkpyTrunc(")))
        self.assertIsNone(applogs.python_line(
            lines, "Screen_homeActivity.java", _java_line(java, "setContentView(")))
        self.assertIsNone(applogs.python_line(lines, "ApkpyValues.java", 10))

    def test_the_crash_shows_the_line_of_writehere(self):
        files, lines = _built()
        java = files["java/Screen_homeActivity.java"]
        click = _java_line(java, "public void onClick(")
        line = _java_line(java, "ApkpyValues.toInt(", after=click)
        f = applogs.Follower(PKG, lines=lines)
        f.pids.add("4321")
        crash = [at(4321, "E", "AndroidRuntime", m) for m in (
            "FATAL EXCEPTION: main",
            "Process: com.example.notes, PID: 4321",
            "ValueError: invalid literal for int() with base 10: 'x'",
            "\tat com.apkpy.app.ApkpyValues.toInt(ApkpyValues.java:150)",
            "\tat com.apkpy.app.Screen_homeActivity$1.onClick(Screen_homeActivity.java:%d)" % line,
            "\tat android.view.View.performClick(View.java:7448)",
        )]
        self.assertEqual(shown(f, crash), [
            "",
            "The app stopped with an error:",
            "  ValueError: invalid literal for int() with base 10: 'x'",
            "    at writehere.py, line 13: n = int(field.get_value())  "
            "(Screen_homeActivity.java:%d)" % line,
        ])

    def test_a_call_shows_each_python_line_once_innermost_first(self):
        files, lines = _built()
        java = files["java/Screen_homeActivity.java"]
        inner = _java_line(java, "String total =")
        click = _java_line(java, "public void onClick(")
        outer = _java_line(java, "pythonCallback_add(", after=click)
        f = applogs.Follower(PKG, lines=lines)
        f.pids.add("4321")
        crash = [at(4321, "E", "AndroidRuntime", m) for m in (
            "FATAL EXCEPTION: main",
            "OverflowError: long overflow",
            "\tat java.lang.Math.addExact(Math.java:883)",
            "\tat com.apkpy.app.Screen_homeActivity.pythonCallback_add(Screen_homeActivity.java:%d)" % inner,
            "\tat com.apkpy.app.Screen_homeActivity._apkpyHelper(Screen_homeActivity.java:%d)" % inner,
            "\tat com.apkpy.app.Screen_homeActivity$1.onClick(Screen_homeActivity.java:%d)" % outer,
        )]
        out = shown(f, crash)
        self.assertEqual([o.split("  (")[0] for o in out[3:]], [
            "    at writehere.py, line 8: total = a + b",
            "    at writehere.py, line 17: out.set_value(str(add(n, 1)))",
        ])

    def test_without_a_map_the_java_lines_are_shown_as_before(self):
        f = applogs.Follower(PKG)
        f.pids.add("4321")
        self.assertIn("    at com.example.notes.Screen_homeActivity$3.onClick(Screen_homeActivity.java:812)",
                      shown(f, CRASH))

    def test_a_frame_the_map_does_not_know_stays_java(self):
        _files, lines = _built()
        f = applogs.Follower(PKG, lines=lines)
        f.pids.add("4321")
        out = shown(f, [at(4321, "E", "AndroidRuntime", m) for m in (
            "FATAL EXCEPTION: main",
            "java.lang.IllegalStateException: boom",
            "\tat com.apkpy.app.Screen_homeActivity.onResume(Screen_homeActivity.java:3)",
            "\tat com.apkpy.app.ApkpyRowAdapter.onBind(ApkpyRowAdapter.java:40)",
        )])
        self.assertEqual(out[3:], [
            "    at com.apkpy.app.Screen_homeActivity.onResume(Screen_homeActivity.java:3)"])

    def test_the_map_is_read_from_apkpy_home(self):
        import json
        import os
        import shutil
        import tempfile
        home = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(home, "lines"))
            with open(os.path.join(home, "lines", PKG + ".json"), "w", encoding="utf-8") as f:
                json.dump({"version": 1, "java": {}, "text": {}}, f)
            with mock.patch("apkpy_lib.native_build.apkpy_home", return_value=home):
                self.assertEqual(applogs.load_lines(PKG), {"version": 1, "java": {}, "text": {}})
                self.assertIsNone(applogs.load_lines("com.other.app"))
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def test_the_build_keeps_the_map_outside_the_project(self):
        import os
        import shutil
        import tempfile
        from apkpy_lib import cli
        home, build = tempfile.mkdtemp(), tempfile.mkdtemp()
        try:
            with mock.patch("apkpy_lib.native_build.apkpy_home", return_value=home), \
                    mock.patch("click.echo"):
                cli._generate_android_project(APP, os.path.join(build, "p"), "Notes",
                                              config={"application_id": PKG, "name": "Notes",
                                                      "version_code": 1, "version_name": "1.0"})
            self.assertTrue(os.path.isfile(os.path.join(home, "lines", PKG + ".json")))
            self.assertFalse(os.path.exists(os.path.join(build, "p", "apkpy")))
        finally:
            shutil.rmtree(home, ignore_errors=True)
            shutil.rmtree(build, ignore_errors=True)


class WhichProcess(unittest.TestCase):

    def test_a_reopen_is_followed_under_its_new_pid(self):
        f = applogs.Follower(PKG)
        again = START.replace("4321", "5555")
        self.assertEqual(shown(f, [START, DIED, again, at(5555, "I", "apkpy", "back")]), [
            "-- com.example.notes started (pid 4321) --",
            "-- com.example.notes stopped --",
            "-- com.example.notes started (pid 5555) --",
            "back",
        ])

    def test_a_package_that_only_starts_the_same_is_not_ours(self):
        f = applogs.Follower(PKG)
        other = START.replace("com.example.notes/", "com.example.notesplus/", 1)
        self.assertEqual(shown(f, [other, at(4321, "I", "apkpy", "not ours")]), [])

    def test_a_second_process_of_the_app_is_ours(self):
        f = applogs.Follower(PKG)
        worker = START.replace("4321:com.example.notes/", "4400:com.example.notes:sync/")
        self.assertEqual(shown(f, [worker]), ["-- com.example.notes started (pid 4400) --"])

    def test_lines_before_the_pid_was_known_are_shown_once_it_is(self):
        # No "Start proc" line (some phones keep it to themselves): the pid
        # comes from pidof, a second or so later, after the first prints.
        f = applogs.Follower(PKG)
        self.assertEqual(shown(f, [at(4321, "I", "apkpy", "first"),
                                   at(999, "I", "apkpy", "not ours"),
                                   at(4321, "I", "apkpy", "second")]), [])
        self.assertEqual(f.started("4321"), ["-- com.example.notes started (pid 4321) --",
                                             "first", "second"])
        self.assertEqual(f.started("4321"), [])


class _Logcat(object):
    """Stands in for `adb logcat`: these lines, then the end of the stream."""

    def __init__(self, lines):
        self.stdout = io.BytesIO("".join(lines).encode("utf-8"))
        self.terminated = False

    def terminate(self):
        self.terminated = True


class Following(unittest.TestCase):

    def test_it_waits_for_the_app_then_says_when_logcat_ends(self):
        said = []
        stream = _Logcat([START, at(4321, "I", "apkpy", "olá, mundo")])
        with mock.patch.object(applogs, "pids_of", return_value=set()), \
                mock.patch.object(applogs.subprocess, "Popen", return_value=stream):
            code = applogs.follow("adb", "R5CT", PKG, say=said.append)
        self.assertEqual(code, 1)
        self.assertTrue(stream.terminated)
        self.assertEqual(said, [
            "Waiting for com.example.notes on R5CT: open the app on the phone. Ctrl+C to stop.",
            "-- com.example.notes started (pid 4321) --",
            "olá, mundo",
            "logcat stopped: is the phone still connected?",
        ])

    def test_an_app_already_open_is_followed_from_the_start(self):
        said = []
        stream = _Logcat([at(4321, "I", "apkpy", "tick")])
        with mock.patch.object(applogs, "pids_of", return_value={"4321"}), \
                mock.patch.object(applogs.subprocess, "Popen", return_value=stream):
            applogs.follow("adb", "R5CT", PKG, say=said.append)
        self.assertEqual(said[:2], [
            "Showing what com.example.notes prints on R5CT (pid 4321). Ctrl+C to stop.",
            "tick"])


class TheCommand(unittest.TestCase):

    def run_logs(self, phones, *args):
        with mock.patch.object(applogs, "find_adb", return_value="adb"), \
                mock.patch.object(applogs, "devices", return_value=phones), \
                mock.patch.object(applogs, "follow", return_value=0) as follow:
            result = CliRunner().invoke(main, ["logs", "--app", PKG] + list(args))
        return result, follow

    def test_no_phone(self):
        result, follow = self.run_logs([])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("No phone found", result.output)
        follow.assert_not_called()

    def test_a_phone_that_has_not_allowed_this_computer(self):
        result, _ = self.run_logs([("R5CT", "unauthorized")])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("accept 'Allow USB debugging'", result.output)

    def test_one_phone_is_followed(self):
        result, follow = self.run_logs([("R5CT", "device")])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(follow.call_args[0][1:3], ("R5CT", PKG))

    def test_two_phones_the_first_unless_one_is_named(self):
        phones = [("R5CT", "device"), ("emulator-5554", "device")]
        result, follow = self.run_logs(phones)
        self.assertIn("2 phones connected; showing R5CT", result.output)
        result, follow = self.run_logs(phones, "--device", "emulator-5554")
        self.assertEqual(follow.call_args[0][1], "emulator-5554")
        result, follow = self.run_logs(phones, "--device", "nope")
        self.assertEqual(result.exit_code, 1)
        follow.assert_not_called()

    def test_no_adb(self):
        with mock.patch.object(applogs, "find_adb", return_value=None):
            result = CliRunner().invoke(main, ["logs", "--app", PKG])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("apkpy setup", result.output)


if __name__ == "__main__":
    unittest.main()
