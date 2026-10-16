# -*- coding: utf-8 -*-
"""The app locks itself, and the phone's own lock opens it again.

    app_lock.after(5)       app_lock.now()      app_lock.off()
    if app_lock.locked(): ...

Four calls of the same table as the rest of the kit. What these tests hold:
the phone and the desk read the minutes, when the app is due to lock and the
prompt's title in the same way; each call is one line of the app, and the
manifest gets the provider that starts the lock with the process; what
cannot be built is refused in the same words on both sides; and on the desk
the lock can be walked through: the cover, the prompt, away and back,
untouched, a Previewer opened again.
"""

import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

import apkpy_lib
from apkpy_lib import job_rules, ui
from apkpy_lib import kit_rules as rules
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import kit
from apkpy_lib.diagnostics import ApkpyError
from apkpy_lib.features import biometrics as replica

from test_data_rules import TOOLING
from test_kit import HEAD, TAIL, _built, _error, _java
from test_real_screens import Previewed

# text -> app_lock.after(): the minutes, or -1 for no number of minutes
MINUTES = [
    ("5", 5.0), ("0", 0.0), ("0.5", 0.5), (" 2 ", 2.0), ("-0", 0.0), ("1440", 1440.0),
    ("-1", -1.0), ("-0.5", -1.0), ("", -1.0), ("soon", -1.0), ("5 min", -1.0),
    ("True", -1.0), ("0,5", -1.0), ("nan", -1.0), ("inf", -1.0),
]
# (left_at, now, minutes) -> due: locked as the app comes back
DUE = [
    ((0, 1000, 5), True),                   # never told when it left
    ((-1, 1000, 5), True),
    ((5000, 4000, 5), True),                # the clock went backwards
    ((1000, 1000 + 299999, 5), False),
    ((1000, 1000 + 300000, 5), True),
    ((1000, 1000, 0), True),                # 0: every time it comes back
    ((1000, 1000 + 29999, 0.5), False),
    ((1000, 1000 + 30000, 0.5), True),
]
# (title, app name) -> what the prompt says
TITLES = [
    (("", "Ledger"), "Unlock Ledger"),
    (("  Open the vault ", "Ledger"), "Open the vault"),
    (("", ""), "Unlock the app"),
    (("", "  Ora  "), "Unlock Ora"),
]
# app name -> what the cover says
HEADINGS = [("Ledger", "Ledger is locked"), ("", "The app is locked"), ("  Ora ", "Ora is locked")]


class _Isolated(unittest.TestCase):
    """Where the Previewer keeps the rule: a folder of the test's own."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="apkpy-app-lock-")
        self._old_path = ui.storage._path
        ui.storage._path = os.path.join(self.folder, "apkpy_storage.json")
        lock = apkpy_lib.app_lock
        lock.secure = True
        lock._forget_window()
        lock._window = None

    def tearDown(self):
        lock = apkpy_lib.app_lock
        lock.secure = True
        lock._forget_window()
        lock._window = None
        ui.storage._path = self._old_path
        shutil.rmtree(self.folder, ignore_errors=True)

    def kept(self):
        path = os.path.join(self.folder, rules.APP_LOCK_FILE)
        if not os.path.exists(path):
            return None
        with io.open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def keep(self, **values):
        with io.open(os.path.join(self.folder, rules.APP_LOCK_FILE), "w", encoding="utf-8") as handle:
            json.dump(values, handle)


class TheRules(unittest.TestCase):
    """What the minutes are, when the app is due, what the prompt says."""

    def test_minutes_are_a_number_from_nothing(self):
        for text, wanted in MINUTES:
            self.assertEqual(rules.app_lock_minutes(text), wanted, repr(text))
        self.assertEqual(rules.app_lock_minutes(5), 5.0)
        self.assertEqual(rules.app_lock_minutes(0.25), 0.25)
        self.assertEqual(rules.app_lock_minutes(True), rules.APP_LOCK_INVALID)
        self.assertEqual(rules.app_lock_minutes(None), rules.APP_LOCK_INVALID)

    def test_due_as_it_comes_back(self):
        for (left_at, now, minutes), wanted in DUE:
            self.assertEqual(rules.app_lock_due(left_at, now, minutes), wanted,
                             (left_at, now, minutes))

    def test_the_prompt_says_the_apps_name(self):
        for (title, name), wanted in TITLES:
            self.assertEqual(rules.app_lock_title(title, name), wanted)
        self.assertEqual(rules.APP_LOCK_WORDS["title"] % "Ledger", "Unlock Ledger")
        for name, wanted in HEADINGS:
            self.assertEqual(rules.app_lock_heading(name), wanted)

    def test_the_phone_says_the_same_words(self):
        source = kit.java_source("ApkpyAppLock", "p")
        for key in ("heading", "line", "button"):
            self.assertIn('"%s"' % rules.APP_LOCK_WORDS[key], source)

    @unittest.skipUnless(TOOLING[0], "no JDK on this machine")
    def test_the_two_languages_agree(self):
        lines = []
        for index, (text, _wanted) in enumerate(MINUTES):
            lines.append('System.out.println("m%d|" + ApkpyKitRules.appLockMinutes("%s"));'
                         % (index, text))
        for index, ((left_at, now, minutes), _wanted) in enumerate(DUE):
            lines.append('System.out.println("d%d|" + ApkpyKitRules.appLockDue(%dL, %dL, %r));'
                         % (index, left_at, now, float(minutes)))
        for index, ((title, name), _wanted) in enumerate(TITLES):
            lines.append('System.out.println("t%d|" + ApkpyKitRules.appLockTitle("%s", "%s"));'
                         % (index, title, name))
        for index, (name, _wanted) in enumerate(HEADINGS):
            lines.append('System.out.println("h%d|" + ApkpyKitRules.appLockHeading("%s"));'
                         % (index, name))
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-app-lock-rules-")
        try:
            with io.open(os.path.join(work, "ApkpyKitRules.java"), "w", encoding="utf-8") as handle:
                handle.write(kit.java_source("ApkpyKitRules", "p").replace("package p;", ""))
            with io.open(os.path.join(work, "Harness.java"), "w", encoding="utf-8") as handle:
                handle.write("public class Harness {\n    public static void main(String[] a) {\n"
                             + "\n".join("        " + line for line in lines) + "\n    }\n}\n")
            built = subprocess.run([javac, "-encoding", "UTF-8", "-d", work,
                                    os.path.join(work, "ApkpyKitRules.java"),
                                    os.path.join(work, "Harness.java")],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([java_bin, "-cp", work, "Harness"], capture_output=True,
                                 text=True, encoding="utf-8")
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        answers = dict(line.split("|", 1) for line in ran.stdout.splitlines())
        self.assertEqual(len(answers), len(MINUTES) + len(DUE) + len(TITLES) + len(HEADINGS))
        for index, (name, wanted) in enumerate(HEADINGS):
            self.assertEqual(answers["h%d" % index], wanted, name)
        for index, (text, wanted) in enumerate(MINUTES):
            self.assertEqual(float(answers["m%d" % index]), wanted, repr(text))
        for index, (case, wanted) in enumerate(DUE):
            self.assertEqual(answers["d%d" % index], str(wanted).lower(), case)
        for index, (case, wanted) in enumerate(TITLES):
            self.assertEqual(answers["t%d" % index], wanted, case)


class WhatIsBuilt(unittest.TestCase):

    BODY = ('app_lock.after(5)\n'
            'app_lock.after(0.5, title="Open the vault")\n'
            'app_lock.now()\n'
            'app_lock.off()\n'
            'if app_lock.locked():\n'
            '    out.set_value("locked")')

    def test_each_call_is_one_line_of_the_class(self):
        java = _java(self.BODY)
        for line in ("return ApkpyAppLock.after(this, minutes, title);",
                     "return ApkpyAppLock.now(this);",
                     "return ApkpyAppLock.off(this);",
                     "return ApkpyAppLock.locked(this);"):
            self.assertIn(line, java)
        self.assertIn('_apkpyNative_app_lock_after(String.valueOf(5), String.valueOf(""))', java)
        self.assertIn('_apkpyNative_app_lock_after(String.valueOf(0.5), '
                      'String.valueOf("Open the vault"))', java)
        # A yes/no crosses as Python's word for it.
        self.assertIn('_apkpyNative_app_lock_locked())).equals("True")', java)

    def test_the_process_starts_the_lock(self):
        files = _built(self.BODY)
        manifest = files["AndroidManifest.xml"]
        self.assertIn('<provider android:name=".ApkpyAppLockStart" '
                      'android:authorities="${applicationId}.apkpy.applock" '
                      'android:exported="false" />', manifest)
        self.assertEqual(manifest.count("ApkpyAppLockStart"), 1)
        # The phone's own prompt: a normal permission, nobody is asked.
        self.assertIn('android.permission.USE_BIOMETRIC', manifest)
        for name in ("ApkpyAppLock", "ApkpyAppLockStart", "ApkpyKitRules"):
            self.assertIn("java/%s.java" % name, files)
        for other in ("ApkpyDisplay", "ApkpyTimers", "ApkpyKitActivity"):
            self.assertNotIn("java/%s.java" % other, files)

    def test_an_app_with_none_of_it_has_none_of_it(self):
        files = _built('out.set_value("x")')
        self.assertFalse([name for name in files if "AppLock" in name])
        self.assertNotIn("<provider", files["AndroidManifest.xml"])
        self.assertNotIn("USE_BIOMETRIC", files["AndroidManifest.xml"])

    def test_a_name_the_app_made_its_own_is_left_alone(self):
        files = _built('app_lock.set_value("on")',
                       top='app_lock = label("off", id="app_lock", screen=home)\n')
        self.assertNotIn("java/ApkpyAppLock.java", files)

    def test_the_classes_are_written_for_the_app(self):
        files = _built(self.BODY)
        for name in ("ApkpyAppLock", "ApkpyAppLockStart"):
            source = files["java/%s.java" % name]
            self.assertTrue(source.startswith("package "))
            self.assertNotIn("__PACKAGE__", source)
        lock = files["java/ApkpyAppLock.java"]
        # The phone draws the prompt and checks the person: nothing typed
        # ever reaches the app.
        self.assertIn("BiometricPrompt", lock)
        self.assertIn("DEVICE_CREDENTIAL", lock)
        self.assertIn("createConfirmDeviceCredentialIntent", lock)
        self.assertNotIn("EditText", lock)


class WhatStopsTheBuild(unittest.TestCase):

    def _stops(self, body, *words, top="", code="U2048"):
        text = _error(body, top)
        self.assertIn(code, text)
        for word in words:
            self.assertIn(word, text)
        return text

    def test_minutes_that_are_not_a_number_from_nothing(self):
        text = self._stops('app_lock.after(-5)',
                           "app_lock.after(): minutes= is a number from 0, got '-5'",
                           "0 locks it every time the app comes back")
        self.assertIn("/guides/app-lock/", text)
        self._stops('app_lock.after("soon")', "got 'soon'")

    def test_what_is_worked_out_while_the_app_runs_is_passed_on(self):
        java = _java('app_lock.after(minutes)', top='minutes = "-3"\n')
        self.assertIn("_apkpyNative_app_lock_after(String.valueOf(minutes)", java)

    def test_what_is_written_wrong(self):
        self._stops('app_lock.after()', "app_lock.after() needs minutes")
        self._stops('app_lock.now(5)', "app_lock.now() takes no arguments, got 1")
        self._stops('app_lock.after(5, on_result=answered)', "app_lock.after() has no on_result=")

    def test_a_call_that_does_not_exist(self):
        self._stops('app_lock.lock()', "app_lock has no lock()",
                    "app_lock has: after(), now(), off(), locked().")
        self._stops('app_lock.unlock()', "app_lock has no unlock()")

    def test_it_is_said_by_a_function_not_by_the_top_of_the_file(self):
        for line in ('app_lock.after(5)', 'app_lock.now()', 'app_lock.off()'):
            source = HEAD + line + '\n\ndef go():\n    out.set_value("x")\n' + TAIL
            text = " ".join(translate_python_to_android(source)["error.txt"].split())
            self.assertIn("U2048", text)
            self.assertIn("%s at the top of the file runs before there is a screen"
                          % (line.split("(")[0] + "()"), text)
            self.assertIn("lifecycle(home, on_mount=opened)", text)
            self.assertIn("the rule is kept on the phone", text)

    def test_said_as_the_first_screen_opens(self):
        source = (HEAD + 'def opened():\n    app_lock.after(5)\n\n'
                  'lifecycle(home, on_mount=opened)\n\ndef go():\n    out.set_value("x")\n' + TAIL)
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files)
        self.assertIn("ApkpyAppLock.after(this, minutes, title)",
                      files["java/Screen_homeActivity.java"])

    def test_inside_a_background_job(self):
        source = (HEAD +
                  'def work(job):\n'
                  '    app_lock.now()\n\n'
                  'sync = background_job("sync", run=work)\n'
                  'def go():\n'
                  '    sync.enqueue()\n' + TAIL)
        text = " ".join(translate_python_to_android(source).get("error.txt", "").split())
        self.assertIn("J7004", text)
        self.assertIn("app_lock.now() cannot run inside a background job", text)


class OnTheDesk(_Isolated):
    """With no window: what the calls answer, and what is kept."""

    def test_what_each_answers_and_what_is_kept(self):
        lock = apkpy_lib.app_lock
        self.assertEqual(lock.after(5), "ok")
        self.assertEqual(self.kept()["minutes"], 5.0)
        self.assertEqual(lock.after("0.5", title=" Open "), "ok")
        self.assertEqual((self.kept()["minutes"], self.kept()["title"]), (0.5, "Open"))
        self.assertEqual(lock.after(-1), "invalid")
        self.assertEqual(lock.after("soon"), "invalid")
        self.assertEqual(self.kept()["minutes"], 0.5)       # a wrong one changes nothing
        self.assertIs(lock.locked(), False)
        self.assertEqual(lock.off(), "ok")
        self.assertIsNone(self.kept())
        for word in ("ok", "invalid", "no_lock"):
            self.assertIn(word, lock.reasons)

    def test_now_locks_and_off_opens(self):
        lock = apkpy_lib.app_lock
        self.assertEqual(lock.now(), "ok")
        self.assertIs(lock.locked(), True)
        self.assertTrue(self.kept()["locked"])
        self.assertEqual(lock.off(), "ok")
        self.assertIs(lock.locked(), False)

    def test_a_phone_with_no_screen_lock(self):
        lock = apkpy_lib.app_lock
        lock.secure = False
        self.assertEqual(lock.after(5), "no_lock")
        self.assertEqual(self.kept()["minutes"], 5.0)       # kept: it holds once one is set
        self.assertEqual(lock.now(), "no_lock")
        self.assertIs(lock.locked(), False)

    def test_the_rule_is_not_the_apps_storage(self):
        apkpy_lib.app_lock.after(5)
        ui.storage.clear()
        self.assertEqual(self.kept()["minutes"], 5.0)

    def test_the_top_of_the_file_is_refused_in_the_builds_words(self):
        for line in ("app_lock.after(5)", "app_lock.now()", "app_lock.off()",
                     "app_lock.locked()"):
            with self.assertRaises(ApkpyError) as raised:
                exec("from apkpy_lib import *\n" + line, {})
            self.assertEqual(raised.exception.code, "U2048")
            self.assertIn("at the top of the file runs before there is a screen",
                          str(raised.exception))

    def test_a_job_body_is_refused_with_the_builds_words(self):
        lock = apkpy_lib.app_lock
        with job_rules.running_job():
            for call in (lambda: lock.after(5), lock.now, lock.off, lock.locked):
                with self.assertRaises(ApkpyError) as raised:
                    call()
                self.assertEqual(raised.exception.code, "J7004")


class InThePreviewer(_Isolated):
    """The window open: the cover, the prompt, away and back, untouched."""

    APP = ('home = Screen(id="home")\n'
           'detail = Screen(id="detail")\n'
           'out = label("Home", id="out", screen=home)\n'
           'label("Detail", id="title", screen=detail)\n'
           'def rule(minutes):\n'
           '    return app_lock.after(minutes)\n'
           'def lock():\n'
           '    return app_lock.now()\n'
           'def stop():\n'
           '    return app_lock.off()\n'
           'def asked():\n'
           '    return app_lock.locked()\n')

    def setUp(self):
        super().setUp()
        self.prompts = []
        self._old_prompt = replica._show_prompt
        replica._show_prompt = lambda prompt, answered: self.prompts.append((prompt, answered))

    def tearDown(self):
        replica._show_prompt = self._old_prompt
        super().tearDown()

    def covered(self):
        cover = apkpy_lib.app_lock._cover
        try:
            return cover is not None and bool(cover.winfo_exists())
        except Exception:
            return False

    def answer(self, success):
        _prompt, answered = self.prompts[-1]
        answered(success, "ok" if success else "cancelled")

    def test_locked_now_the_cover_and_the_phones_prompt(self):
        with Previewed(self.APP, "") as shown:
            self.assertEqual(shown.ns["lock"](), "ok")
            shown.settle(0.1)
            self.assertTrue(self.covered())
            self.assertEqual(len(self.prompts), 1)
            prompt = self.prompts[0][0]
            # The phone's own: a fingerprint, a face, or the PIN.
            self.assertTrue(prompt["allow_pin"])
            self.assertTrue(prompt["title"].startswith("Unlock "))
            self.answer(True)
            shown.settle(0.1)
            self.assertFalse(self.covered())
            self.assertIs(shown.ns["asked"](), False)

    def test_cancelled_it_stays_locked_and_the_button_asks_again(self):
        with Previewed(self.APP, "") as shown:
            shown.ns["lock"]()
            self.answer(False)
            shown.settle(0.1)
            self.assertTrue(self.covered())
            self.assertIs(shown.ns["asked"](), True)
            apkpy_lib.app_lock._ask()               # what the cover's button does
            self.assertEqual(len(self.prompts), 2)
            self.answer(True)
            self.assertFalse(self.covered())

    def test_the_cover_stays_over_another_screen(self):
        with Previewed(self.APP, "") as shown:
            shown.ns["lock"]()
            shown.app.render_screen(shown.ns["detail"])
            shown.settle(0.1)
            self.assertTrue(self.covered())
            cover = apkpy_lib.app_lock._cover
            # Above everything the screen drew.
            self.assertEqual(cover.master.winfo_children()[-1], cover)

    def test_back_while_locked_does_not_leave_the_screen(self):
        with Previewed(self.APP, "") as shown:
            shown.app.render_screen(shown.ns["detail"])
            shown.ns["lock"]()
            self.assertEqual(shown.app._system_back(), "break")
            self.assertIs(shown.app._active_screen, shown.ns["detail"])

    def test_away_and_back(self):
        with Previewed(self.APP, "") as shown:
            lock = apkpy_lib.app_lock
            self.assertEqual(shown.ns["rule"](5), "ok")
            lock._went_away()
            self.assertGreater(self.kept()["left_at"], 0)
            lock._came_back()                   # back within the five minutes
            self.assertIs(lock.locked(), False)
            self.assertEqual(self.kept()["left_at"], 0)
            lock._went_away()
            self.keep(minutes=5, title="", left_at=time.time() * 1000 - 6 * 60000)
            lock._came_back()                   # six minutes later
            self.assertIs(lock.locked(), True)
            self.assertTrue(self.covered())
            self.assertEqual(len(self.prompts), 1)

    def test_zero_locks_every_time_it_comes_back(self):
        with Previewed(self.APP, "") as shown:
            lock = apkpy_lib.app_lock
            shown.ns["rule"](0)
            lock._went_away()
            lock._came_back()
            self.assertIs(lock.locked(), True)

    def test_untouched_for_the_minutes(self):
        with Previewed(self.APP, "") as shown:
            shown.ns["rule"](0.004)             # about a quarter of a second
            shown.settle(0.1)
            self.assertIs(apkpy_lib.app_lock.locked(), False)
            shown.settle(0.6)
            self.assertIs(apkpy_lib.app_lock.locked(), True)
            self.assertTrue(self.covered())

    def test_a_touch_starts_the_count_again(self):
        with Previewed(self.APP, "") as shown:
            lock = apkpy_lib.app_lock
            shown.ns["rule"](0.01)              # six tenths of a second
            for _ in range(6):
                shown.settle(0.2)
                lock._touched()
            self.assertIs(lock.locked(), False)
            shown.settle(1.0)
            self.assertIs(lock.locked(), True)

    def test_a_previewer_opened_again_is_the_app_opened_again(self):
        # Closed twenty minutes ago with a five-minute rule: locked as it opens.
        self.keep(minutes=5, title="", left_at=time.time() * 1000 - 20 * 60000)
        with Previewed(self.APP, ""):
            self.assertIs(apkpy_lib.app_lock.locked(), True)
            self.assertTrue(self.covered())

    def test_opened_again_soon_it_is_open(self):
        self.keep(minutes=5, title="", left_at=time.time() * 1000 - 60000)
        with Previewed(self.APP, ""):
            self.assertIs(apkpy_lib.app_lock.locked(), False)

    def test_locked_when_it_was_closed_is_locked_when_it_opens(self):
        self.keep(minutes=5, title="", left_at=time.time() * 1000, locked=True)
        with Previewed(self.APP, ""):
            self.assertIs(apkpy_lib.app_lock.locked(), True)

    def test_the_first_time_it_is_said_the_app_is_not_locked_at_once(self):
        app = self.APP + ('def opened():\n'
                          '    app_lock.after(0)\n'
                          'lifecycle(home, on_mount=opened)\n')
        with Previewed(app, ""):
            self.assertEqual(self.kept()["minutes"], 0.0)
            self.assertIs(apkpy_lib.app_lock.locked(), False)

    def test_off_opens_and_forgets(self):
        with Previewed(self.APP, "") as shown:
            shown.ns["rule"](0)
            shown.ns["lock"]()
            self.assertEqual(shown.ns["stop"](), "ok")
            self.assertFalse(self.covered())
            self.assertIsNone(self.kept())
            apkpy_lib.app_lock._went_away()
            apkpy_lib.app_lock._came_back()
            self.assertIs(apkpy_lib.app_lock.locked(), False)

    def test_no_screen_lock_nothing_is_locked(self):
        with Previewed(self.APP, "") as shown:
            apkpy_lib.app_lock.secure = False
            self.assertEqual(shown.ns["rule"](0), "no_lock")
            self.assertEqual(shown.ns["lock"](), "no_lock")
            apkpy_lib.app_lock._went_away()
            apkpy_lib.app_lock._came_back()
            self.assertIs(apkpy_lib.app_lock.locked(), False)
            self.assertFalse(self.covered())


if __name__ == "__main__":
    unittest.main()
