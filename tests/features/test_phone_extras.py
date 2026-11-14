# -*- coding: utf-8 -*-
"""Seven calls of the phone's own apps and services, on both sides.

gallery.save(), clock.alarm() and clock.timer(), display.on_screenshot(),
phone.call(), calendar.events(), clipboard.paste() and clipboard.has_text(),
and notify(at=, repeat=) -- a reminder that posts with the app closed.

The rules each call reads its arguments by are written twice, in Python for
the Previewer and in Java for the phone, and read here against each other.
"""

import datetime
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import apkpy_lib
from apkpy_lib import kit_rules as rules
from apkpy_lib import field_rules
from apkpy_lib import ui
from apkpy_lib.core.compiler import _audit_accessibility, translate_python_to_android
from apkpy_lib.core.features import kit
from apkpy_lib.core.features import notifications as notifications_contract
from apkpy_lib.core.style_parser import _parse_style_blocks
from apkpy_lib.diagnostics import ApkpyError
from apkpy_lib.features import kit as preview
from apkpy_lib.features import notifications as preview_notifications

from test_data_rules import TOOLING
from test_kit import _built, _error, _files, _java

EPOCH = datetime.datetime(1970, 1, 1)
NOW = datetime.datetime(2026, 11, 7, 15, 20, 30)


def _millis(moment):
    return (moment - EPOCH) // datetime.timedelta(milliseconds=1)


def _manifest(body, top=""):
    return _built(body, top)["AndroidManifest.xml"]


APP = '''from apkpy_lib import *
home = Screen(id="home")
def go():
    %s
button("Go", id="go", screen=home, command=go)
run(start_screen=home)
'''


def _app(line):
    return translate_python_to_android(APP % line)


# on_screenshot() takes a function written at the top of the file, as an app's.
_TOLD = []


def shot():
    _TOLD.append(1)


class TheTwoLanguagesReadAlike(unittest.TestCase):
    """Every rule the seven calls share, run in Java and in Python."""

    clocks = [("7", "30"), ("23", "59"), ("0", "0"), ("24", "0"), ("-1", "0"), ("7", "60"),
              ("7.0", "30"), ("7.5", "0"), ("x", "0"), ("", "0"), (" 7 ", "05")]
    seconds = ["1", "0", "86400", "86401", "90", "90.0", "-5", "abc", "", " 300 "]
    windows = [("", ""), ("2026-11-10", ""), ("2026-11-10 09:00", ""), ("", "2026-11-09"),
               ("2026-11-10", "2026-11-10"), ("2026-11-10 09:00", "2026-11-10 08:00"),
               ("nope", ""), ("", "nope"), ("2026-11-10", "2026-11-12 12:00"),
               ("2026-02-30", ""), ("", "2026-11-07 10:00")]
    names = ["a.jpg", "A.JPEG", "photo.PNG", "x.webp", "clip.mp4", "clip.MOV", "doc.pdf",
             "noext", "", " b.heic ", "a.tar.gz", "dir.v/x", "x.", "x.3gp", "song.mp3"]
    repeats = ["", "daily", "Weekly", " daily ", "hourly", "DAILY", "week"]
    times = ["09:00", "15:20", "15:21", "9:05", "24:00", "23:60", "2026-11-07 09:00",
             "2026-11-08 09:00", "2026-11-08", "tomorrow", "", " 18:45 ",
             "2026-11-07T16:00", "123:00", "0:00", "07:5"]
    nexts = [(NOW.replace(hour=9, minute=0, second=0) - datetime.timedelta(days=3), "daily"),
             (NOW - datetime.timedelta(days=20), "weekly"),
             (NOW + datetime.timedelta(hours=1), "daily"),
             (NOW.replace(hour=9, minute=0, second=0), ""),
             (NOW.replace(hour=9, minute=0, second=0), "hourly"),
             (NOW.replace(second=30), "daily")]

    def test_the_rules(self):
        if not TOOLING:
            self.skipTest("no JDK on this machine")

        def literal(text):
            return '"' + "".join("\\u%04x" % ord(ch) for ch in text) + '"'

        utc = 'java.util.TimeZone.getTimeZone("UTC")'
        now = _millis(NOW)
        lines = []
        for index, (hour, minute) in enumerate(self.clocks):
            lines.append('System.out.println("alarm|%d|" + java.util.Arrays.toString('
                         'ApkpyKitRules.clockAlarm(%s, %s)));' % (index, literal(hour), literal(minute)))
        for index, text in enumerate(self.seconds):
            lines.append('System.out.println("seconds|%d|" + ApkpyKitRules.clockSeconds(%s));'
                         % (index, literal(text)))
        for index, (start, end) in enumerate(self.windows):
            lines.append('System.out.println("window|%d|" + java.util.Arrays.toString('
                         'ApkpyKitRules.calendarWindow(%s, %s, %dL, %s)));'
                         % (index, literal(start), literal(end), now, utc))
        for index, text in enumerate(self.names):
            lines.append('System.out.println("type|%d|" + ApkpyKitRules.galleryType(%s));'
                         % (index, literal(text)))
        for index, text in enumerate(self.repeats):
            lines.append('System.out.println("repeat|%d|" + ApkpyKitRules.reminderRepeat(%s));'
                         % (index, literal(text)))
        for index, text in enumerate(self.times):
            lines.append('System.out.println("at|%d|" + ApkpyKitRules.reminderAt(%s, %dL, %s));'
                         % (index, literal(text), now, utc))
        for index, (due, repeat) in enumerate(self.nexts):
            lines.append('System.out.println("next|%d|" + ApkpyKitRules.reminderNext(%dL, %s, %dL, %s));'
                         % (index, _millis(due), literal(repeat), now, utc))

        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-extras-rules-")
        self.addCleanup(shutil.rmtree, work, True)
        with io.open(os.path.join(work, "ApkpyKitRules.java"), "w", encoding="utf-8") as handle:
            handle.write(kit.java_source("ApkpyKitRules", "p").replace("package p;", ""))
        with io.open(os.path.join(work, "Harness.java"), "w", encoding="utf-8") as handle:
            handle.write("public class Harness {\n    public static void main(String[] a) {\n        "
                         + "\n        ".join(lines) + "\n    }\n}\n")
        built = subprocess.run([javac, "-encoding", "UTF-8", "-d", work,
                                os.path.join(work, "ApkpyKitRules.java"),
                                os.path.join(work, "Harness.java")],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java_bin, "-cp", work, "Harness"],
                             capture_output=True, text=True, encoding="ascii")
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)

        nothing = str(-2 ** 63)
        seen = 0
        for line in ran.stdout.splitlines():
            kind, index, answer = line.split("|", 2)
            index = int(index)
            seen += 1
            if kind == "alarm":
                found = rules.clock_alarm(*self.clocks[index])
                self.assertEqual(answer, "null" if found is None else str(list(found)),
                                 self.clocks[index])
            elif kind == "seconds":
                found = rules.clock_seconds(self.seconds[index])
                self.assertEqual(int(answer), -1 if found is None else found, self.seconds[index])
            elif kind == "window":
                found = rules.calendar_window(*self.windows[index], now=NOW)
                wanted = "null" if found is None else str([_millis(found[0]), _millis(found[1])])
                self.assertEqual(answer, wanted, self.windows[index])
            elif kind == "type":
                self.assertEqual(answer, rules.gallery_type(self.names[index]), self.names[index])
            elif kind == "repeat":
                found = rules.reminder_repeat(self.repeats[index])
                self.assertEqual(answer, "null" if found is None else found, self.repeats[index])
            elif kind == "at":
                found = rules.reminder_at(self.times[index], NOW)
                self.assertEqual(answer, nothing if found is None else str(_millis(found)),
                                 self.times[index])
            elif kind == "next":
                due, repeat = self.nexts[index]
                found = rules.reminder_next(due, repeat, NOW)
                self.assertEqual(answer, nothing if found is None else str(_millis(found)),
                                 self.nexts[index])
        self.assertEqual(seen, len(lines))

    def test_what_the_rules_say(self):
        self.assertEqual(rules.clock_alarm(7, 30), (7, 30))
        self.assertIsNone(rules.clock_alarm(24, 0))
        self.assertEqual(rules.clock_seconds(480), 480)
        self.assertIsNone(rules.clock_seconds(0))
        # Nothing given is the week from the start of today.
        self.assertEqual(rules.calendar_window("", "", NOW),
                         (datetime.datetime(2026, 11, 7), datetime.datetime(2026, 11, 14)))
        # An end with no hour is the whole of that day.
        self.assertEqual(rules.calendar_window("2026-11-10", "2026-11-10", NOW)[1],
                         datetime.datetime(2026, 11, 11))
        self.assertEqual(rules.gallery_type("clip.MOV"), "video/quicktime")
        self.assertEqual(rules.gallery_type("doc.pdf"), "")
        # "09:00" is the next 09:00; a time already gone today is tomorrow's.
        self.assertEqual(rules.reminder_at("18:45", NOW), datetime.datetime(2026, 11, 7, 18, 45))
        self.assertEqual(rules.reminder_at("09:00", NOW), datetime.datetime(2026, 11, 8, 9, 0))
        self.assertIsNone(rules.reminder_at("2026-11-08", NOW))
        self.assertEqual(rules.reminder_next(datetime.datetime(2026, 11, 1, 9), "weekly", NOW),
                         datetime.datetime(2026, 11, 8, 9))


class WhatIsWritten(unittest.TestCase):
    """Each call is one line into a class of ApkPy's, and the manifest asks
    for what that class needs -- and nothing for a call the app does not make."""

    def test_a_call(self):
        java = _java('phone.call("+351 912 345 678", on_result=answered)')
        self.assertIn("ApkpyCall.call(this, number, new ApkpyKit.Done()", java)
        manifest = _manifest('phone.call("+351 912 345 678", on_result=answered)')
        self.assertIn('android.permission.CALL_PHONE', manifest)
        # A tablet with no phone in it can still install the app.
        self.assertIn('<uses-feature android:name="android.hardware.telephony" '
                      'android:required="false" />', manifest)

    def test_the_calendar_is_read(self):
        files = _built('calendar.events(on_result=answered)')
        self.assertIn("ApkpyCalendar.events(this, start, end, new ApkpyKit.Done()",
                      files["java/Screen_homeActivity.java"])
        self.assertIn("android.permission.READ_CALENDAR", files["AndroidManifest.xml"])
        self.assertNotIn("WRITE_CALENDAR", files["AndroidManifest.xml"])
        self.assertIn("java/ApkpyCalendar.java", files)

    def test_the_clock(self):
        for line, call in (('out.set_value(clock.alarm(7, 30, "Wake"))',
                            "ApkpyClock.alarm(this, hour, minute, label)"),
                           ('out.set_value(clock.timer(90))',
                            "ApkpyClock.timer(this, seconds, label)")):
            files = _built(line)
            self.assertIn(call, files["java/Screen_homeActivity.java"])
            self.assertIn('com.android.alarm.permission.SET_ALARM', files["AndroidManifest.xml"])
            # Handed to the clock app: nothing waits for an answer.
            self.assertNotIn("java/ApkpyKitActivity.java", files)

    def test_the_gallery(self):
        files = _built('gallery.save("a.jpg", album="Trip", on_result=answered)')
        self.assertIn("ApkpyGallery.save(this, path, album, new ApkpyKit.Done()",
                      files["java/Screen_homeActivity.java"])
        # Android 10 and later need no permission to add to the gallery.
        self.assertIn('android.permission.WRITE_EXTERNAL_STORAGE" android:maxSdkVersion="28"',
                      files["AndroidManifest.xml"])
        self.assertNotIn("READ_MEDIA_IMAGES", files["AndroidManifest.xml"])

    def test_the_clipboard_asks_for_nothing(self):
        for line, call in (('out.set_value(clipboard.paste())', "ApkpyClipboard.paste(this)"),
                           ('if clipboard.has_text():\n    out.set_value("y")',
                            "ApkpyClipboard.hasText(this)")):
            files = _built(line)
            self.assertIn(call, files["java/Screen_homeActivity.java"])
            self.assertNotIn("uses-permission", files["AndroidManifest.xml"].replace(
                "android.permission.INTERNET", ""))

    def test_a_screenshot(self):
        top = 'def shot():\n    out.set_value("s")\n\n'
        files = _built('display.on_screenshot(shot)', top)
        java = files["java/Screen_homeActivity.java"]
        self.assertIn("ApkpyDisplay.onScreenshot(this, run)", java)
        # The function is found by its name on the screen that asked.
        self.assertIn("_apkpyScreenshotCalls = ApkpyDisplay.host(this", java)
        self.assertIn("pythonCallback_shot()", java)
        self.assertIn("android.permission.DETECT_SCREEN_CAPTURE", files["AndroidManifest.xml"])

    def test_the_older_calls_of_the_two_families_are_untouched(self):
        for line in ('clipboard.copy("hi")', 'gallery.pick(on_result=answered)'):
            files = _built(line)
            self.assertNotIn("java/ApkpyGallery.java", files, line)
            self.assertNotIn("java/ApkpyClipboard.java", files, line)
            self.assertNotIn("java/ApkpyKit.java", files, line)

    def test_none_of_it_when_none_is_used(self):
        files = _built('out.set_value("x")')
        for name in ("ApkpyCall", "ApkpyCalendar", "ApkpyClock", "ApkpyGallery", "ApkpyClipboard"):
            self.assertNotIn("java/%s.java" % name, files)
        for word in ("CALL_PHONE", "READ_CALENDAR", "SET_ALARM", "DETECT_SCREEN_CAPTURE",
                     "WRITE_EXTERNAL_STORAGE", "RECEIVE_BOOT_COMPLETED"):
            self.assertNotIn(word, files["AndroidManifest.xml"])


class WhatStopsTheBuild(unittest.TestCase):

    def test_a_call_made_at_the_top(self):
        files = translate_python_to_android(
            'from apkpy_lib import *\nhome = Screen(id="home")\n'
            'def shot():\n    pass\n'
            'display.on_screenshot(shot)\nrun(start_screen=home)\n')
        self.assertIn("error.txt", files)
        self.assertIn("on_screenshot", files["error.txt"])

    def test_a_clock_time_written_wrong(self):
        self.assertIn("clock.alarm", _error('out.set_value(clock.alarm(7, 30, 5, 6))'))

    def test_a_field_type_that_does_not_exist(self):
        files = translate_python_to_android(
            'from apkpy_lib import *\nhome = Screen(id="home")\n'
            'inputs("Phone number", id="number", type="telephone", screen=home)\n'
            'run(start_screen=home)\n')
        error = " ".join(files["error.txt"].split())
        # type="phone" itself is a field since 1.15 (the keyboard for it).
        self.assertIn('inputs() has no type="telephone"', error)
        self.assertIn('Did you mean type="phone"?', error)
        files = translate_python_to_android(
            'from apkpy_lib import *\nhome = Screen(id="home")\n'
            'inputs("Secret", type="pasword", screen=home)\n'
            'run(start_screen=home)\n')
        self.assertIn('Did you mean type="password"?', " ".join(files["error.txt"].split()))


class Reminders(unittest.TestCase):
    """notify(at=) on the phone: kept, and Android's alarm set for when it is due."""

    def test_a_reminder_is_written_with_its_time(self):
        files = _app('notify("Stretch", "Stand up", id="s", at="09:00", repeat="daily")')
        self.assertNotIn("error.txt", files, files.get("error.txt"))
        java = files["java/Screen_homeActivity.java"]
        self.assertIn('"at", String.valueOf("09:00")', java)
        self.assertIn('"repeat", String.valueOf("daily")', java)
        native = files["java/ApkpyNotifications.java"]
        self.assertIn("class ReminderReceiver", native)
        self.assertIn("class RestartReceiver", native)
        self.assertIn("java/ApkpyKitRules.java", files)
        manifest = files["AndroidManifest.xml"]
        self.assertIn("android.permission.RECEIVE_BOOT_COMPLETED", manifest)
        self.assertIn('.ApkpyNotifications$ReminderReceiver', manifest)
        self.assertIn('android.intent.action.BOOT_COMPLETED', manifest)
        self.assertIn('android.intent.action.MY_PACKAGE_REPLACED', manifest)
        # The permission sits before <application>, the receivers inside it.
        self.assertLess(manifest.index("RECEIVE_BOOT_COMPLETED"), manifest.index("<application"))
        self.assertLess(manifest.index("ReminderReceiver"), manifest.index("</application>"))
        # Exact alarms are a permission the person grants in Settings: not asked.
        self.assertNotIn("SCHEDULE_EXACT_ALARM", manifest)
        self.assertNotIn("USE_EXACT_ALARM", manifest)

    def test_a_time_typed_by_the_person_is_read_on_the_phone(self):
        files = translate_python_to_android(
            'from apkpy_lib import *\nhome = Screen(id="home")\n'
            'when = inputs("A time", id="when", screen=home)\n'
            'def go():\n    notify("A", "B", id="r", at=when.get_value())\n'
            'button("Go", id="go", screen=home, command=go)\nrun(start_screen=home)\n')
        self.assertNotIn("error.txt", files, files.get("error.txt"))
        self.assertIn("class ReminderReceiver", files["java/ApkpyNotifications.java"])

    def test_a_notification_with_no_time_is_as_it_was(self):
        files = _app('notify("A", "B", id="r")')
        self.assertNotIn("error.txt", files, files.get("error.txt"))
        native = files["java/ApkpyNotifications.java"]
        for word in ("ReminderReceiver", "RestartReceiver", "ApkpyKitRules", "schedule(",
                     "apkpy_reminders", "AlarmManager"):
            self.assertNotIn(word, native)
        self.assertNotIn("java/ApkpyKitRules.java", files)
        self.assertNotIn('"at"', files["java/Screen_homeActivity.java"])
        manifest = files["AndroidManifest.xml"]
        self.assertNotIn("RECEIVE_BOOT_COMPLETED", manifest)
        self.assertIn("DismissReceiver", manifest)
        self.assertNotIn("ReminderReceiver", manifest)

    def test_to_the_minute_is_asked_for_in_the_manifest(self):
        files = _app('notify("A", "B", id="r", at="09:00", repeat="daily", exact=True)')
        self.assertNotIn("error.txt", files, files.get("error.txt"))
        manifest = files["AndroidManifest.xml"]
        self.assertIn('<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />',
                      manifest)
        self.assertLess(manifest.index("SCHEDULE_EXACT_ALARM\""), manifest.index("<application"))
        # When the person allows it, the reminders waiting are set again.
        receiver = manifest[manifest.index("RestartReceiver"):]
        receiver = receiver[:receiver.index("</receiver>")]
        self.assertIn("android.app.action.SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED", receiver)
        self.assertIn('"exact", "true"', files["java/Screen_homeActivity.java"])
        native = files["java/ApkpyNotifications.java"]
        self.assertIn('if (flag(spec, "exact")) askExact(c);', native)
        self.assertIn("Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM", native)
        # Neither a reminder without it, nor a notification with no time.
        for line in ('notify("A", "B", id="r", at="09:00")',
                     'notify("A", "B", id="r", at="09:00", exact=False)', 'notify("A", "B", id="r")'):
            files = _app(line)
            self.assertNotIn("SCHEDULE_EXACT_ALARM", files["AndroidManifest.xml"], line)
            self.assertNotIn('"exact"', files["java/Screen_homeActivity.java"], line)

    def test_a_reminder_is_set_again_when_the_app_opens(self):
        # Android forgets an app's alarms when it is stopped from Settings, or
        # by a phone that cleans up; opening the app sets them again.
        native = _app('notify("A", "B", id="r", at="09:00")')["java/ApkpyNotifications.java"]
        attach = native[native.index("public static void attach"):]
        self.assertIn("rearm(a.getApplicationContext());", attach[:attach.index("registerActivity")])
        plain = _app('notify("A", "B", id="r")')["java/ApkpyNotifications.java"]
        self.assertNotIn("rearm(", plain)
        self.assertNotIn("forgot its alarms", plain)

    def test_what_stops_the_build(self):
        for line, words in (
                ('notify("A", "B", exact=True)', "needs its time"),
                ('notify("A", "B", at="09:00", exact=flag)', "notify(exact=) is True or False"),
                ('notify("A", "B", at="09:00", exact="yes")', "notify(exact=) is True or False"),
                ('notify("A", "B", at="25:00")', "notify(at=) is a time"),
                ('notify("A", "B", at="2026-11-08")', "notify(at=) is a time"),
                ('notify("A", "B", at=9)', "notify(at=) is a time"),
                ('notify("A", "B", at="09:00", repeat="hourly")', "notify(repeat=)"),
                ('notify("A", "B", repeat="daily")', "needs the time of the first"),
                ('notify("A", "B", at="09:00", repeat=kind)', "notify(repeat=)")):
            files = _app(line)
            self.assertIn("error.txt", files, line)
            self.assertIn(words, " ".join(files["error.txt"].split()), line)


class OnTheDesk(unittest.TestCase):
    """The Previewer's twins, with no window: every call answers."""

    def setUp(self):
        self.heard = []
        self.answer = lambda ok, value: self.heard.append((ok, value))
        granted = set(ui.permissions._granted)
        self.addCleanup(lambda: (ui.permissions._granted.clear(),
                                 ui.permissions._granted.update(granted)))
        self.home = tempfile.mkdtemp(prefix="apkpy-desk-home-")
        self.addCleanup(shutil.rmtree, self.home, True)

    def test_the_clock(self):
        clock = preview.ClockAPI()
        self.assertEqual(clock.alarm(7, 30, "Wake up"), "ok")
        self.assertEqual(clock.last, ("alarm", 7, 30, "Wake up"))
        self.assertEqual(clock.alarm("6"), "ok")
        self.assertEqual(clock.last, ("alarm", 6, 0, ""))
        self.assertEqual(clock.alarm(24), "invalid")
        self.assertEqual(clock.timer(480, "Pasta"), "ok")
        self.assertEqual(clock.last, ("timer", 480, "Pasta"))
        self.assertEqual(clock.timer(0), "invalid")
        self.assertEqual(clock.timer(86401), "invalid")
        self.assertIs(apkpy_lib.clock, preview.clock)

    def test_a_call(self):
        phone = preview.PhoneAPI()
        phone.call("+351 912 345 678", on_result=self.answer)
        self.assertEqual(self.heard, [(True, "ok")])
        self.assertEqual(phone.last, ("call", "+351912345678"))
        phone.call("no number", on_result=self.answer)
        self.assertEqual(self.heard[-1], (False, "invalid"))

    def test_the_calendar(self):
        calendar = preview.CalendarAPI()
        calendar.events(on_result=self.answer)
        ok, value = self.heard[-1]
        self.assertTrue(ok)
        events = json.loads(value)
        self.assertTrue(events)
        for event in events:
            self.assertEqual(set(event), {"title", "start", "end", "all_day", "location",
                                          "notes", "calendar"})
        calendar.events("2026-11-10", "2026-11-09", on_result=self.answer)
        self.assertEqual(self.heard[-1], (False, "invalid"))

    def test_the_made_up_week_is_the_phones_shape(self):
        rows = preview._calendar_sample(datetime.datetime(2026, 11, 7),
                                        datetime.datetime(2026, 11, 14))
        self.assertEqual([row["title"] for row in rows],
                         ["Team meeting", "Dentist", "Ana's birthday", "Gym"])
        self.assertEqual(rows[0]["start"], "2026-11-07 10:00")
        self.assertEqual(rows[0]["end"], "2026-11-07 10:45")
        # A whole day is written as a day, its end the last day it covers.
        self.assertEqual((rows[2]["start"], rows[2]["end"], rows[2]["all_day"]),
                         ("2026-11-10", "2026-11-10", True))
        one_day = preview._calendar_sample(datetime.datetime(2026, 11, 7),
                                           datetime.datetime(2026, 11, 8))
        self.assertEqual([row["title"] for row in one_day], ["Team meeting"])

    def test_the_gallery_is_a_folder(self):
        picture = os.path.join(self.home, "lake.jpg")
        with open(picture, "wb") as handle:
            handle.write(b"\xff\xd8\xff")
        with patch.dict(os.environ, {"USERPROFILE": self.home, "HOME": self.home}):
            apkpy_lib.gallery.save(picture, album="Trip", on_result=self.answer)
            apkpy_lib.gallery.save(picture, album="Trip", on_result=self.answer)
            apkpy_lib.gallery.save(picture, album="a/b", on_result=self.answer)
        folder = os.path.join(self.home, ".apkpy", "gallery")
        self.assertEqual(self.heard, [(True, "lake.jpg"), (True, "lake-2.jpg"), (True, "lake.jpg")])
        self.assertTrue(os.path.isfile(os.path.join(folder, "Trip", "lake-2.jpg")))
        self.assertTrue(os.path.isfile(os.path.join(folder, "a_b", "lake.jpg")))
        document = os.path.join(self.home, "terms.pdf")
        open(document, "w").close()
        preview.gallery_save(document, on_result=self.answer)
        self.assertEqual(self.heard[-1], (False, "invalid"))
        preview.gallery_save(os.path.join(self.home, "gone.jpg"), on_result=self.answer)
        self.assertEqual(self.heard[-1], (False, "not_found"))

    def test_the_clipboard(self):
        self.assertEqual(apkpy_lib.clipboard.paste(), "")
        self.assertIs(apkpy_lib.clipboard.has_text(), False)

        class Root:
            text = "hello"

            def clipboard_get(self):
                if self.text is None:
                    raise RuntimeError("CLIPBOARD selection doesn't exist")
                return self.text

        root = Root()
        with patch.object(preview, "_root", return_value=root):
            self.assertEqual(apkpy_lib.clipboard.paste(), "hello")
            self.assertIs(apkpy_lib.clipboard.has_text(), True)
            root.text = None
            self.assertEqual(apkpy_lib.clipboard.paste(), "")
            self.assertIs(apkpy_lib.clipboard.has_text(), False)

    def test_a_screenshot(self):
        display = preview.DisplayAPI()
        del _TOLD[:]
        self.assertEqual(display.on_screenshot(shot), "ok")
        self.assertEqual(display.on_screenshot(shot), "ok")     # once, by its name
        self.assertEqual(display._screenshot(), 1)
        self.assertEqual(_TOLD, [1])
        display._closed(None)
        self.assertEqual(display._screenshot(), 0)
        with self.assertRaises(ApkpyError):
            exec("display.on_screenshot(shot)", {"display": display, "shot": shot})

    def test_a_field_type_that_does_not_exist(self):
        with self.assertRaises(ApkpyError) as raised:
            apkpy_lib.inputs("Phone number", type="telephone")
        self.assertIn('inputs() has no type="telephone"', str(raised.exception))
        for kind in field_rules.ALL_TYPES:
            field_rules.check_known(kind)


class RemindersOnTheDesk(unittest.TestCase):

    def setUp(self):
        self.api = preview_notifications.NotificationsAPI()
        for patcher in (patch.object(preview_notifications, "notifications", self.api),
                        patch.object(ui, "live_preview_root", return_value=None),
                        patch.object(ui, "live_preview", return_value=None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_with_no_previewer_it_is_said(self):
        preview_notifications.notify("Stretch", "Stand up", id="s", at="18:45")
        self.assertIn("s", self.api.scheduled)
        self.assertEqual(self.api.items, {})
        self.api.cancel("s")
        self.assertNotIn("s", self.api.scheduled)

    def test_what_is_refused(self):
        for kw in (dict(at="25:00"), dict(at="2026-11-08"), dict(at=9),
                   dict(at="09:00", repeat="hourly"), dict(repeat="daily")):
            with self.assertRaises(ValueError, msg=kw):
                preview_notifications.notify("A", "B", id="r", **kw)
        self.assertEqual(dict(self.api.scheduled), {})

    def test_it_posts_when_due_and_comes_back_the_next_day(self):
        waits = []
        with patch.object(preview, "_root", return_value=object()), \
                patch.object(preview, "_later", lambda seconds, work: waits.append((seconds, work))):
            preview_notifications.notify("Gone", "x", id="once", at="2020-01-01 09:00")
            preview_notifications.notify("Daily", "x", id="daily", at="2020-01-01 09:00",
                                         repeat="daily")
            self.assertEqual([seconds for seconds, _ in waits], [0.0, 0.0])
            for _, work in list(waits):
                work()
        self.assertEqual(set(self.api.items), {"once", "daily"})
        self.assertNotIn("once", self.api.scheduled)
        following = self.api.scheduled["daily"]["due"]
        self.assertGreater(following, datetime.datetime.now())
        self.assertEqual((following.hour, following.minute), (9, 0))
        self.assertEqual(len(waits), 3)
        self.assertLessEqual(waits[-1][0], 86400.0)

    def test_to_the_minute_asks_once(self):
        sheets = []

        class Sheet:
            def __init__(self, *args, **kw):
                self.args, self.kw = args, kw
                sheets.append(self)

            def open(self):
                return self

        granted = set(ui.permissions._granted)
        self.addCleanup(lambda: (ui.permissions._granted.clear(),
                                 ui.permissions._granted.update(granted)))
        from apkpy_lib.features import kit_surfaces
        with patch.object(preview, "_root", return_value=object()), \
                patch.object(preview, "_later", lambda seconds, work: None), \
                patch.object(kit_surfaces, "Handover", Sheet):
            preview_notifications.notify("A", "x", id="a", at="09:00", exact=True)
            preview_notifications.notify("B", "x", id="b", at="10:00", exact=True)
            preview_notifications.notify("C", "x", id="c", at="11:00")
        self.assertEqual(set(self.api.scheduled), {"a", "b", "c"})
        self.assertEqual(len(sheets), 1)                       # once, not per reminder
        self.assertEqual(sheets[0].args[:3], ("permission", "alarm", "Settings"))
        self.assertIn("set alarms and reminders", sheets[0].args[3])
        sheets[0].kw["on_choice"]("always")
        self.assertIn("SCHEDULE_EXACT_ALARM", ui.permissions._granted)

    def test_to_the_minute_is_for_a_reminder(self):
        for kw in (dict(exact=True), dict(at="09:00", exact="yes"), dict(at="09:00", exact=1)):
            with self.assertRaises(ValueError, msg=kw):
                preview_notifications.notify("A", "B", id="r", **kw)
        preview_notifications.notify("A", "B", id="r", exact=False)
        self.assertIn("r", self.api.items)
        self.assertEqual(dict(self.api.scheduled), {})

    def test_a_cancelled_one_does_not_post(self):
        waits = []
        with patch.object(preview, "_root", return_value=object()), \
                patch.object(preview, "_later", lambda seconds, work: waits.append((seconds, work))):
            preview_notifications.notify("A", "x", id="r", at="2020-01-01 09:00")
            self.api.cancel("r")
            waits[0][1]()
        self.assertEqual(dict(self.api.items), {})


class TheContrastOfAnOutlinedButton(unittest.TestCase):
    """An outlined or text button is see-through: its primary words sit on
    what is behind. Read on the primary they were "1.00:1" on every app."""

    def _found(self, card, variant):
        styles = dict(_parse_style_blocks("card { background-color: %s; }" % card))
        styles["__theme__"] = {"primary": "#3B5BDB", "on_primary": "#FFFFFF", "text": "#1C1B1F"}
        screens = {"home": [{"comp_type": "container", "id": "card", "children": [
            {"comp_type": "button", "id": "b", "text": "Timer", "variant": variant}]}]}
        return _audit_accessibility(screens, styles)

    def test_on_a_light_card_it_reads(self):
        for variant in ("outlined", "text", "filled", None):
            self.assertEqual(self._found("#FFFFFF", variant), [], variant)

    def test_on_its_own_colour_it_is_still_said(self):
        found = self._found("#3B5BDB", "outlined")
        self.assertEqual(len(found), 1)
        self.assertIn("1.00:1", found[0][2])


if __name__ == "__main__":
    unittest.main()
