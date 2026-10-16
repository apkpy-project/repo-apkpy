# -*- coding: utf-8 -*-
"""The calls that reach the rest of the phone.

    haptics.tap()   speech.say("...")   browser.open(url)   phone.dial("...")
    files.save_as(name, text, on_result=saved)   downloads.start(url)
    calendar.add_event(...)   recorder.start()   printing.html(...)
    incoming.links("notes")

One table (apkpy_lib/kit_rules.py) says which calls exist. The compiler turns
each into a native block and writes the Java class behind it; the Previewer
stands in with something a person can see and answer. These tests hold the
two to the table: the same calls with the same arguments, the same words,
Java that javac accepts, and the same reading of the text an app passes.
"""

import inspect
import io
import os
import re
import subprocess
import tempfile
import time
import unittest
import wave

import apkpy_lib
from apkpy_lib import job_rules
from apkpy_lib import kit_rules as rules
from apkpy_lib.core import java_api
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import kit
from apkpy_lib.diagnostics import ApkpyError
from apkpy_lib.features import kit as preview
from apkpy_lib.features import kit_surfaces

from test_data_rules import TOOLING
from test_real_screens import Previewed

JAR, _LEVELS = java_api.find_android_jar()
needs_sdk = unittest.skipUnless(JAR and TOOLING[0], "no Android SDK or JDK on this machine")

HEAD = (
    'from apkpy_lib import *\n'
    'home = Screen(id="home")\n'
    'out = label("", id="out", screen=home)\n'
    '\n'
    'def answered(ok, value):\n'
    '    out.set_value(value)\n'
    '\n'
)
TAIL = ('\nbutton("Go", id="go", screen=home, command=go)\n'
        'run(start_screen=home)\n')

OBJECTS = {
    "haptics": apkpy_lib.haptics, "speech": apkpy_lib.speech, "browser": apkpy_lib.browser,
    "files": apkpy_lib.files, "downloads": apkpy_lib.downloads,
    "calendar": apkpy_lib.calendar, "phone": apkpy_lib.phone,
    "recorder": apkpy_lib.recorder, "printing": apkpy_lib.printing,
    "incoming": apkpy_lib.incoming,
    "home_widget": apkpy_lib.home_widget, "quick_tile": apkpy_lib.quick_tile,
    "ads": apkpy_lib.ads, "updates": apkpy_lib.updates, "health": apkpy_lib.health,
    "timer": apkpy_lib.timer, "network": apkpy_lib.network,
    "display": apkpy_lib.display,
    "app_lock": apkpy_lib.app_lock,
}


def _files(body, top="", tail=TAIL):
    lines = "\n".join("    " + line for line in body.strip("\n").split("\n"))
    return translate_python_to_android(HEAD + top + "def go():\n" + lines + "\n" + tail)


def _built(body, top=""):
    files = _files(body, top)
    if "error.txt" in files:
        raise AssertionError(files["error.txt"][:900])
    return files


def _java(body, top=""):
    return _built(body, top)["java/Screen_homeActivity.java"]


def _error(body, top="", tail=TAIL):
    """The rendered diagnostic, flattened to one line."""
    text = _files(body, top, tail).get("error.txt")
    if text is None:
        raise AssertionError("it built")
    return " ".join(text.split())


class TheTable(unittest.TestCase):
    """What both sides read. A call the table has and one side lacks is how
    the phone and the desk come to disagree."""

    def test_every_call_exists_on_the_desk_with_the_same_arguments(self):
        for namespace in rules.SPEC:
            for name in rules.verbs(namespace):
                method = getattr(OBJECTS[namespace], name)
                written = []
                for argument, parameter in inspect.signature(method).parameters.items():
                    written.append(argument if parameter.default is parameter.empty
                                   else "%s=%r" % (argument, parameter.default))
                shown = ("%s.%s(%s)" % (namespace, name, ", ".join(written))).replace("'", '"')
                self.assertEqual(shown, rules.signature(namespace, name))

    def test_the_desk_has_no_call_the_table_lacks(self):
        for namespace, api in OBJECTS.items():
            if namespace == "files":
                continue            # older than the table, with verbs of its own
            public = {name for name, value in vars(type(api)).items()
                      if callable(value) and not name.startswith("_")}
            public -= {"folder"}    # where the desk keeps what the phone keeps elsewhere
            self.assertEqual(public - set(rules.verbs(namespace)), set(), namespace)

    def test_every_word_the_java_answers_is_in_the_table(self):
        known = set()
        for namespace in rules.SPEC:
            known |= set(rules.reasons(namespace))
        folder = os.path.dirname(kit.__file__)
        # libs/ holds the classes written against a library the family brings.
        found = [os.path.join(folder, file) for file in sorted(os.listdir(folder))]
        found += [os.path.join(folder, "libs", file)
                  for file in sorted(os.listdir(os.path.join(folder, "libs")))]
        for path in found:
            file = os.path.basename(path)
            if not file.endswith(".java") or file in ("ApkpyKitRules.java",):
                continue
            with io.open(path, encoding="utf-8") as handle:
                source = handle.read()
            answered = set(re.findall(r'answer\([^;]*?,\s*(?:true|false),\s*"([a-z_]+)"\)', source))
            answered |= set(re.findall(r'return\s+"([a-z_]+)";', source))
            for pair in re.findall(r'\?\s*"([a-z_]+)"\s*:\s*"([a-z_]+)"', source):
                answered |= set(pair)
            answered |= set(re.findall(r'ended\(id,\s*(?:true|false),\s*"([a-z_]+)"\)', source))
            self.assertEqual(answered - known, set(), file)

    def test_every_family_says_what_its_words_mean(self):
        for namespace, spec in rules.SPEC.items():
            self.assertIn("ok", spec["reasons"], namespace)
            for word, meaning in spec["reasons"].items():
                self.assertRegex(word, r"^[a-z_]+$")
                self.assertTrue(meaning.endswith("."), (namespace, word))


class WhatIsWritten(unittest.TestCase):
    """Each call becomes one line into a class of ApkPy's."""

    def test_a_call_is_a_native_block_one_line_long(self):
        java = _java("haptics.tap()")
        self.assertIn("/** haptics.tap() -- written by ApkPy */", java)
        self.assertIn("private String _apkpyNative_haptics_tap() {\n"
                      '        return ApkpyHaptics.feedback(this, "tap");\n    }', java)
        self.assertIn("_apkpyNative_haptics_tap();", java)
        self.assertIn("// --- calls to the phone", java)
        self.assertNotIn("the app author's Java", java)

    def test_the_arguments_take_their_places_and_the_rest_are_filled_in(self):
        java = _java('speech.say("Hello", rate=1.2, on_result=answered)')
        self.assertIn(
            '_apkpyNative_speech_say(String.valueOf("Hello"), String.valueOf(""), '
            'String.valueOf(1.2), String.valueOf("1.0"), _apkpyNativeMain(', java)
        self.assertIn("pythonCallback_answered(ok, value);", java)
        # ok is a real boolean in the callback, not the text "True".
        self.assertRegex(java, r"void pythonCallback_answered\(boolean \w+, String \w+\)")

    def test_an_answer_that_comes_later_is_dropped_once_the_screen_is_gone(self):
        java = _java('speech.say("Hello")')
        self.assertIn("if (!isDestroyed()) done.run(ok, value);", java)

    def test_a_word_is_a_value(self):
        java = _java('out.set_value("dial: " + phone.dial("912 345 678"))')
        self.assertIn('"dial: " + _apkpyNativeText(_apkpyNative_phone_dial('
                      'String.valueOf("912 345 678")))', java)

    def test_a_yes_or_no_is_asked_of_the_word(self):
        java = _java('if recorder.is_recording() and not speech.is_speaking():\n'
                     '    out.set_value(str(haptics.available()))')
        self.assertIn('_apkpyNative_recorder_is_recording())).equals("True")', java)
        self.assertIn('!(String.valueOf(_apkpyNativeText(_apkpyNative_speech_is_speaking()))'
                      '.equals("True"))', java)
        # Where it is a value it is Python's own spelling of one.
        self.assertIn("String.valueOf(_apkpyNativeText(_apkpyNative_haptics_available()))", java)
        self.assertIn('return ApkpyKit.flag(', kit.java_source("ApkpyHaptics", "p"))

    def test_a_call_handed_over_as_a_command(self):
        files = _built("pass", top='button("Feel", id="feel", screen=home, '
                                   'command=haptics.success)\n'
                                   'button("Buzz", id="buzz", screen=home, '
                                   'command=lambda: haptics.vibrate(300))\n')
        java = files["java/Screen_homeActivity.java"]
        self.assertIn("_apkpyNative_haptics_success();", java)
        self.assertIn("_apkpyNative_haptics_vibrate(String.valueOf(300));", java)

    def test_only_what_is_used_is_written(self):
        files = _built("haptics.tap()")
        classes = sorted(name for name in files if name.startswith("java/Apkpy"))
        self.assertEqual(classes, ["java/ApkpyHaptics.java", "java/ApkpyKit.java",
                                   "java/ApkpyKitRules.java", "java/ApkpyWeight.java"])
        java = files["java/Screen_homeActivity.java"]
        self.assertNotIn("haptics_vibrate", java)
        manifest = files["AndroidManifest.xml"]
        # tap() is Android's own effect: no permission. vibrate() runs the motor.
        self.assertNotIn("VIBRATE", manifest)
        self.assertNotIn("ApkpyKitActivity", manifest)
        self.assertIn('android.permission.VIBRATE"',
                      _built("haptics.vibrate(200)")["AndroidManifest.xml"])

    def test_an_app_with_none_of_it_has_none_of_it(self):
        files = _built('out.set_value("hi")')
        self.assertEqual([name for name in files if "Kit" in name], [])
        self.assertNotIn("_apkpyNative", files["java/Screen_homeActivity.java"])

    def test_every_screen_can_make_the_call(self):
        files = _built("haptics.tap()", top='other = Screen(id="other")\n')
        self.assertIn("_apkpyNative_haptics_tap()", files["java/Screen_otherActivity.java"])

    def test_beside_an_apps_own_block(self):
        java = _java("out.set_value(battery())\nhaptics.tap()",
                     top='battery = native.java("batteryLevel", code="return \\"1\\";", '
                         'preview=lambda: "1")\n')
        self.assertIn('/** native.java("batteryLevel") -- writehere.py:', java)
        self.assertIn("/** haptics.tap() -- written by ApkPy */", java)
        self.assertIn('The ones marked "written by ApkPy"', java)
        # An app's own block is promised a context; ApkPy's take the Activity.
        self.assertEqual(java.count("final android.content.Context context = this;"), 1)


class TheManifest(unittest.TestCase):

    def test_the_screen_that_waits_is_there_only_for_calls_that_wait(self):
        for body in ('speech.listen(on_result=answered)',
                     'files.save_as("a.txt", "a", on_result=answered)',
                     'files.save_copy("a.txt")', 'recorder.start()'):
            files = _built(body)
            self.assertIn('<activity android:name=".ApkpyKitActivity" android:exported="false"',
                          files["AndroidManifest.xml"], body)
            self.assertIn("java/ApkpyKitActivity.java", files, body)
        self.assertNotIn("ApkpyKitActivity",
                         _built('speech.say("hi")')["AndroidManifest.xml"])

    def test_it_sits_inside_the_application(self):
        manifest = _built('recorder.start()')["AndroidManifest.xml"]
        self.assertLess(manifest.index("<application"), manifest.index(".ApkpyKitActivity"))
        self.assertLess(manifest.index(".ApkpyKitActivity"), manifest.index("</application>"))

    def test_the_microphone_is_asked_for_and_never_required(self):
        manifest = _built('recorder.start()')["AndroidManifest.xml"]
        self.assertIn('<uses-permission android:name="android.permission.RECORD_AUDIO" />',
                      manifest)
        self.assertIn('<uses-feature android:name="android.hardware.microphone" '
                      'android:required="false" />', manifest)
        # Dictation is the recogniser's microphone, not the app's.
        self.assertNotIn("RECORD_AUDIO",
                         _built('speech.listen(on_result=answered)')["AndroidManifest.xml"])

    def test_one_queries_element_names_what_is_looked_for(self):
        manifest = _built('speech.say("hi")\nspeech.listen(on_result=answered)'
                          )["AndroidManifest.xml"]
        self.assertEqual(manifest.count("<queries>"), 1)
        self.assertIn('android.intent.action.TTS_SERVICE', manifest)
        self.assertIn('android.speech.action.RECOGNIZE_SPEECH', manifest)
        self.assertLess(manifest.index("<queries>"), manifest.index("<application"))

    def test_the_internet_is_asked_for_once(self):
        manifest = _built('browser.show("https://example.com")\n'
                          'https.get("https://example.com/a", on_response=answered)'
                          )["AndroidManifest.xml"]
        self.assertEqual(manifest.count('android.permission.INTERNET"'), 1)
        java = _java('browser.show("https://example.com")\n'
                     'https.get("https://example.com/a", on_response=answered)')
        self.assertEqual(java.count("PERMISSION_REQ_INTERNET ="), 1)

    def test_nothing_is_asked_for_to_hand_over(self):
        manifest = _built('phone.dial("1")\nphone.sms("1", "a")\n'
                          'calendar.add_event("a", "2026-01-02")\n'
                          'browser.open("https://example.com")\nprinting.text("a")'
                          )["AndroidManifest.xml"]
        self.assertNotIn("<uses-permission", manifest)
        self.assertNotIn("<queries>", manifest)

    def test_what_may_come_in(self):
        files = _built('out.set_value(incoming.link() + incoming.text() + incoming.file())\n'
                       'incoming.clear()',
                       top='incoming.links("notes")\n'
                           'incoming.links("https", "example.com", preview="https://example.com/a")\n'
                           'incoming.shares("text")\nincoming.shares("image")\n')
        manifest = files["AndroidManifest.xml"]
        self.assertIn('<activity android:name=".ApkpyIncomingActivity" android:exported="true"',
                      manifest)
        self.assertIn('<data android:scheme="notes" />', manifest)
        self.assertIn('<data android:scheme="https" android:host="example.com" />', manifest)
        # Only a web address can be verified against a site.
        self.assertEqual(manifest.count('android:autoVerify="true"'), 1)
        self.assertIn('<data android:mimeType="text/plain" />', manifest)
        self.assertIn('<data android:mimeType="image/*" />', manifest)
        self.assertEqual(manifest.count("android.intent.action.SEND"), 2)
        self.assertIn("java/ApkpyIncomingActivity.java", files)
        # The declarations are the manifest's; nothing of them runs.
        java = files["java/Screen_homeActivity.java"]
        self.assertNotIn("incoming_links", java)
        self.assertIn("return ApkpyIncoming.link(this);", java)


class AnAppsOwnNames(unittest.TestCase):
    """``phone = inputs("Phone")`` is an ordinary thing to write."""

    def test_a_name_the_app_made_its_own_is_left_alone(self):
        files = _built('out.set_value(phone.get_value())',
                       top='phone = inputs("Phone", id="phone", screen=home)\n')
        self.assertEqual([name for name in files if "Kit" in name or "Handoff" in name], [])

    def test_a_modal_called_browser_opens_as_a_modal(self):
        files = _built('browser.open()',
                       top='browser = modal("Pick a browser", content="Which one?", '
                           'id="browser_dialog")\n')
        self.assertNotIn("java/ApkpyBrowser.java", files)

    def test_importing_the_names_is_not_taking_them(self):
        source = ('from apkpy_lib import Screen, button, haptics, run\n'
                  'home = Screen(id="home")\n'
                  'button("Go", id="go", screen=home, command=haptics.tap)\n'
                  'run(start_screen=home)\n')
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:400])
        self.assertIn("java/ApkpyHaptics.java", files)

    def test_the_older_verbs_of_files_are_untouched(self):
        java = _java('out.set_value(files.path("a.txt"))\n'
                     'files.save_as("a.txt", "a", on_result=answered)')
        self.assertIn("getFilesDir()", java)
        self.assertIn("_apkpyNative_files_save_as(", java)


class WhatStopsTheBuild(unittest.TestCase):
    """A mistake in one of these calls is found while the app is built."""

    def _stops(self, body, *words, top="", tail=TAIL):
        text = _error(body, top, tail)
        self.assertIn("U2048", text)
        for word in words:
            self.assertIn(word, text)
        return text

    def test_a_call_that_does_not_exist(self):
        self._stops('speech.speak("hi")', "speech has no speak()", "Did you mean speech.say(")

    def test_an_argument_that_does_not_exist(self):
        self._stops('speech.say("hi", speed=2)', "speech.say() has no speed=")
        self._stops('phone.dial("1", on_result=answered)', "phone.dial() has no on_result=",
                    "answers at once")

    def test_too_few_and_too_many(self):
        self._stops('phone.dial()', "phone.dial() needs number")
        self._stops('haptics.tap(3)', "haptics.tap() takes no arguments, got 1")
        self._stops('speech.say("a", text="b")', "got text twice")

    def test_a_constant_of_the_wrong_kind(self):
        self._stops('haptics.vibrate("long")', "ms= is a number")
        self._stops('calendar.add_event("a", "2026-01-02", all_day="yes")',
                    "all_day= is True or False")

    def test_the_answer_goes_to_a_function_that_takes_it(self):
        self._stops('speech.say("a", on_result=lambda ok, value: None)',
                    "on_result= has to be a function you defined")
        self._stops('speech.say("a", on_result=one)', "one() is handed two things",
                    "def one(ok, value):", top="def one(ok):\n    pass\n\n")

    def test_brackets(self):
        self._stops('out.set_value(recorder.seconds)', "recorder.seconds() is missing its brackets")
        self._stops("pass", "phone.dial() is handed over without being called",
                    top='button("Dial", id="d", screen=home, command=phone.dial)\n')

    def test_a_declaration_is_written_once_at_the_top(self):
        self._stops('incoming.links("notes")',
                    "incoming.links() is written once, on a line of its own at the top")
        self._stops("pass", "has to be text written in the source",
                    top='SCHEME = "notes"\nincoming.links(SCHEME)\n')

    def test_what_an_app_may_claim(self):
        self._stops("pass", "tel: already belongs to the phone",
                    top='incoming.links("tel")\n')
        self._stops("pass", "https needs the site as well",
                    top='incoming.links("https")\n')
        self._stops("pass", "a scheme is lower-case letters", top='incoming.links("My App")\n')
        self._stops("pass", 'there is no kind "video"'.replace('"', "'"),
                    top='incoming.shares("video")\n')

    def test_asking_what_came_in_when_nothing_can(self):
        self._stops('out.set_value(incoming.link())', 'would always answer ""',
                    'incoming.links("notes")')
        self._stops('out.set_value(incoming.file())', "no file can be shared into this app",
                    top='incoming.shares("text")\n')

    def test_inside_a_background_job(self):
        source = (HEAD +
                  'def work(job):\n'
                  '    haptics.tap()\n\n'
                  'sync = background_job("sync", run=work)\n'
                  'def go():\n'
                  '    sync.enqueue()\n' + TAIL)
        text = " ".join(translate_python_to_android(source).get("error.txt", "").split())
        self.assertIn("J7004", text)
        self.assertIn("haptics.tap() cannot run inside a background job", text)


@needs_sdk
class TheJava(unittest.TestCase):
    """Every class is Java: javac compiles all of them against android.jar."""

    def test_every_class_compiles(self):
        javac = TOOLING[0]
        work = tempfile.mkdtemp(prefix="apkpy-kit-")
        folder = os.path.join(work, "com", "apkpy", "app")
        os.makedirs(folder)
        paths = []
        for file in sorted(os.listdir(os.path.dirname(kit.__file__))):
            if file.endswith(".java"):
                path = os.path.join(folder, file)
                with io.open(path, "w", encoding="utf-8") as handle:
                    handle.write(kit.java_source(file[:-5], "com.apkpy.app"))
                paths.append(path)
        self.assertGreaterEqual(len(paths), 13)
        done = subprocess.run(
            [javac, "-encoding", "UTF-8", "-source", "8", "-target", "8", "-Xlint:-options",
             "-cp", JAR, "-d", os.path.join(work, "out")] + paths,
            capture_output=True, text=True)
        self.assertEqual(0, done.returncode, (done.stdout + done.stderr)[-3000:])

    def test_no_placeholder_is_left_in_a_class(self):
        for file in os.listdir(os.path.dirname(kit.__file__)):
            if file.endswith(".java"):
                self.assertEqual(re.findall(r"__[A-Z_]+__", kit.java_source(file[:-5], "p")),
                                 [], file)

    def test_the_two_languages_read_the_text_alike(self):
        numbers = ["12", " 12 ", "+12", "-7", "12.0", "12.5", "13.5", "-0.5", "1e3", "1e400",
                   "", "abc", "1_000", "0x10", "12f", "NaN", "Infinity", ".5", "5.",
                   "9223372036854775807", "9.5e18", " 12", "١٢", "true"]
        truths = ["true", "TRUE", " True ", "false", "yes", "1", "", " true", "tru e"]
        moments = ["2026-11-03 15:30", "2026-11-03T15:30:59", "2026-11-03", "2026-2-3 9:05",
                   "2026-02-30", "2024-02-29", "2023-02-29", "1900-02-29", "2000-02-29",
                   "2026-13-01", "2026-00-10", "2026-11-03 24:00", "2026-11-03 15:60",
                   "0000-01-01", "03/11/2026", "2026-11-03 15", " 2026-11-03 ", "", "tomorrow"]
        events = [("2026-11-03 15:30", "", "false"), ("2026-11-03 15:30", "2026-11-03 17:00", "false"),
                  ("2026-11-03 15:30", "2026-11-03 15:30", "false"),
                  ("2026-11-03 15:30", "2026-11-03 10:00", "false"),
                  ("2026-11-03", "", "false"), ("2026-11-03", "2026-11-05", "false"),
                  ("2026-11-03 15:30", "", "true"), ("2026-11-03 15:30", "2026-11-04", "True"),
                  ("2026-11-03", "2026-11-02", "false"), ("nope", "", "false"),
                  ("2026-11-03 15:30", "nope", "false"), ("2026-12-31 23:30", "", "false")]
        webs = ["https://example.com", "HTTP://EXAMPLE.com/a b", " https://example.com/a?b=1 ",
                "ftp://example.com", "https://", "example.com", "https:///a", "https://a b"]
        phones = ["+351 912 345 678", "(21) 555-0100", "abc", "*#06#", "", "+", "12,34;5"]
        pages = ["<h1>Terms</h1>", "<HTML><body>x</body></HTML>", "", "<p>a &lt; b</p>",
                 "<!doctype html><html lang='pt'>café</html>", "said <Html once", "<htm l>"]

        def literal(text):
            return '"' + "".join("\\u%04x" % ord(ch) for ch in text) + '"'

        lines = []
        for index, text in enumerate(numbers):
            lines.append('System.out.println("number|%d|" + ApkpyKitRules.number(%s, -1.5));'
                         % (index, literal(text)))
            lines.append('System.out.println("whole|%d|" + ApkpyKitRules.whole(%s, -3L));'
                         % (index, literal(text)))
        for index, text in enumerate(truths):
            lines.append('System.out.println("truth|%d|" + ApkpyKitRules.truth(%s));'
                         % (index, literal(text)))
        for index, text in enumerate(moments):
            lines.append('System.out.println("when|%d|" + java.util.Arrays.toString('
                         'ApkpyKitRules.when(%s)));' % (index, literal(text)))
        for index, (start, end, all_day) in enumerate(events):
            lines.append('System.out.println("event|%d|" + java.util.Arrays.toString('
                         'ApkpyKitRules.eventTimes(%s, %s, %s, java.util.TimeZone.getTimeZone("UTC"))));'
                         % (index, literal(start), literal(end), literal(all_day)))
        for index, text in enumerate(webs):
            lines.append('System.out.println("web|%d|" + plain(ApkpyKitRules.webAddress(%s)));'
                         % (index, literal(text)))
        for index, text in enumerate(phones):
            lines.append('System.out.println("phone|%d|" + ApkpyKitRules.phoneNumber(%s));'
                         % (index, literal(text)))
        for index, text in enumerate(pages):
            lines.append('System.out.println("page|%d|" + plain(ApkpyKitRules.document(%s, "b{c:d}")));'
                         % (index, literal(text)))

        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-kit-rules-")
        rules_java = kit.java_source("ApkpyKitRules", "p").replace("package p;", "")
        with io.open(os.path.join(work, "ApkpyKitRules.java"), "w", encoding="utf-8") as handle:
            handle.write(rules_java)
        with io.open(os.path.join(work, "Harness.java"), "w", encoding="utf-8") as handle:
            # What comes back is written in ASCII, so it reads the same whatever
            # the console of the machine running the test thinks it is.
            handle.write("public class Harness {\n"
                         "    static String plain(String text) {\n"
                         "        StringBuilder out = new StringBuilder();\n"
                         "        for (char ch : text.toCharArray()) {\n"
                         "            if (ch < 128) out.append(ch);\n"
                         "            else out.append(String.format(\"<%04x>\", (int) ch));\n"
                         "        }\n"
                         "        return out.toString();\n"
                         "    }\n"
                         "    public static void main(String[] a) {\n        "
                         + "\n        ".join(lines) + "\n    }\n}\n")
        built = subprocess.run([javac, "-encoding", "UTF-8", "-d", work,
                                os.path.join(work, "ApkpyKitRules.java"),
                                os.path.join(work, "Harness.java")],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java_bin, "-cp", work, "Harness"],
                             capture_output=True, text=True, encoding="ascii")
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)

        import datetime
        epoch = datetime.datetime(1970, 1, 1)
        seen = 0
        for line in ran.stdout.splitlines():
            kind, index, answer = line.split("|", 2)
            index = int(index)
            seen += 1
            if kind == "number":
                self.assertEqual(float(answer), rules.number(numbers[index], -1.5), numbers[index])
            elif kind == "whole":
                self.assertEqual(int(answer), rules.whole(numbers[index], -3), numbers[index])
            elif kind == "truth":
                self.assertEqual(answer == "true", rules.truth(truths[index]), truths[index])
            elif kind == "when":
                found = rules.when(moments[index])
                if found is None:
                    self.assertEqual(answer, "null", moments[index])
                else:
                    moment, has_time = found
                    self.assertEqual(answer, str([moment.year, moment.month, moment.day,
                                                  moment.hour, moment.minute, moment.second,
                                                  1 if has_time else 0]), moments[index])
            elif kind == "event":
                found = rules.event_times(*events[index])
                if found is None:
                    self.assertEqual(answer, "null", events[index])
                else:
                    begin, finish, whole_day = found
                    wanted = [int((begin - epoch).total_seconds() * 1000),
                              int((finish - epoch).total_seconds() * 1000),
                              1 if whole_day else 0]
                    self.assertEqual(answer, str(wanted), events[index])
            elif kind == "web":
                wanted = "".join(ch if ord(ch) < 128 else "<%04x>" % ord(ch)
                                 for ch in rules.web_address(webs[index]))
                self.assertEqual(answer, wanted, webs[index])
            elif kind == "phone":
                self.assertEqual(answer, rules.phone_number(phones[index]), phones[index])
            elif kind == "page":
                wanted = "".join(ch if ord(ch) < 128 else "<%04x>" % ord(ch)
                                 for ch in rules.document(pages[index], "b{c:d}"))
                self.assertEqual(answer, wanted, pages[index])
        self.assertEqual(seen, len(lines))

    def test_html_an_app_wrote_is_given_a_page_and_a_page_is_left_alone(self):
        whole = "<html><head><style>p{color:red}</style></head><body><p>x</p></body></html>"
        self.assertEqual(rules.document(whole, rules.PRINT_CSS), whole)
        page = rules.document("<h1>Terms</h1>", rules.page_css("#F3F4F8", "#1B1B1F", "#3B5BDB"))
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertIn("width=device-width", page)
        self.assertIn("background:#F3F4F8", page)
        self.assertIn("a{color:#3B5BDB}", page)
        self.assertNotIn("@", page)
        self.assertIn("<body><h1>Terms</h1></body>", page)
        # The same rules reach the phone, and nothing in them needs escaping twice.
        self.assertIn(rules.PAGE_CSS, kit.java_source("ApkpyBrowser", "p"))
        self.assertIn(rules.PRINT_CSS, kit.java_source("ApkpyPrinting", "p"))

    def test_a_webview_never_leaves_the_app_in_the_phones_night_mode(self):
        # Seen on a phone in dark mode with a light app: the first WebView a
        # process makes resets the Activity's resources to the phone's setting.
        made = 0
        for file in os.listdir(os.path.dirname(kit.__file__)):
            if not file.endswith(".java"):
                continue
            lines = kit.java_source(file[:-5], "p").splitlines()
            for index, line in enumerate(lines):
                if "new WebView(" in line and not line.strip().startswith("*"):
                    made += 1
                    self.assertIn("ApkpyKit.mode(activity)", lines[index - 1], file)
                    self.assertIn("mode.keep();", lines[index + 1], file)
        self.assertEqual(made, 2)

    def test_a_window_of_ours_does_not_black_out_the_system_bars(self):
        # The old see-through theme is not asked to draw behind the bars, and
        # Android fills them with black: seen under the microphone prompt.
        for name in ("ApkpyKitActivity", "ApkpyIncomingActivity", "ApkpyBrowser"):
            self.assertIn("ApkpyKit.clearBars(", kit.java_source(name, "p"), name)
        self.assertIn("FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS", kit.java_source("ApkpyKit", "p"))

    def test_haptics_say_off_when_the_owner_switched_that_vibration_off(self):
        # Android reports a request it then ignores as performed. Seen on a
        # phone whose settings screen showed haptic feedback on: the older
        # yes-or-no was 1 and the strength the vibrator obeys was 0.
        java = kit.java_source("ApkpyHaptics", "p")
        self.assertIn("Settings.System.HAPTIC_FEEDBACK_ENABLED", java)
        self.assertIn('"haptic_feedback_intensity"', java)
        self.assertIn('asked && touchOn(activity) ? "ok" : "off"', java)
        # vibrate(ms) is the app's own buzz, with its own switch: left to
        # guess, Android files a short one as touch feedback and drops it.
        self.assertIn("VibrationAttributes.USAGE_MEDIA", java)
        self.assertNotIn("USAGE_TOUCH", java)
        self.assertIn('buzzOn(activity) ? "ok" : "off"', java)


class OnTheDeskWithNoWindow(unittest.TestCase):
    """A script, a test, a build: every call still answers, and none of them
    opens a window or waits for somebody who is not there."""

    def setUp(self):
        self.heard = []
        self.answer = lambda ok, value: self.heard.append((ok, value))

    def test_a_touch(self):
        self.assertEqual(preview.haptics.success(), "ok")
        self.assertEqual(preview.haptics.vibrate("120.0"), "ok")
        self.assertEqual(preview.haptics.last, ("vibrate", 120))
        preview.haptics.vibrate(999999)
        self.assertEqual(preview.haptics.last, ("vibrate", rules.LIMITS["vibrate_ms"][1]))
        preview.haptics.vibrate("soon")
        self.assertEqual(preview.haptics.last, ("vibrate", 200))
        self.assertIs(preview.haptics.available(), True)

    def test_a_voice(self):
        speech = preview.SpeechAPI()
        speech.say("Hello there", on_result=self.answer)
        self.assertEqual(self.heard, [(True, "ok")])
        self.assertIs(speech.is_speaking(), False)
        speech.say("   ", on_result=self.answer)
        self.assertEqual(self.heard[-1], (True, "ok"))
        speech.listen(on_result=self.answer)
        self.assertEqual(self.heard[-1], (False, "cancelled"))
        self.assertEqual(speech.stop(), "ok")

    def test_a_page(self):
        browser = preview.BrowserAPI()
        self.assertEqual(browser.open("https://example.com/a"), "ok")
        self.assertEqual(browser.open("example.com"), "invalid")
        self.assertEqual(browser.open("javascript:alert(1)"), "invalid")
        browser.show(html="<h1>Terms</h1>", title="Terms", on_result=self.answer)
        self.assertEqual(self.heard, [(True, "")])
        browser.show(on_result=self.answer)
        self.assertEqual(self.heard[-1], (False, "invalid"))

    def test_handing_over(self):
        calendar, phone = preview.CalendarAPI(), preview.PhoneAPI()
        self.assertEqual(calendar.add_event("Dentist", "2026-11-03 15:30"), "ok")
        self.assertEqual(calendar.last["finish"] - calendar.last["begin"],
                         __import__("datetime").timedelta(hours=1))
        self.assertEqual(calendar.add_event("Trip", "2026-11-03", "2026-11-05"), "ok")
        self.assertIs(calendar.last["all_day"], True)
        self.assertEqual((calendar.last["finish"] - calendar.last["begin"]).days, 3)
        self.assertEqual(calendar.add_event("Never", "2026-02-30"), "invalid")
        self.assertEqual(calendar.add_event("Back", "2026-11-03 15:30", "2026-11-03 10:00"),
                         "invalid")
        self.assertEqual(phone.dial("+351 912 345 678"), "ok")
        self.assertEqual(phone.last, ("dial", "+351912345678"))
        self.assertEqual(phone.dial("no number"), "invalid")
        self.assertEqual(phone.sms("912 345 678", "On my way"), "ok")
        self.assertEqual(phone.last, ("sms", "912345678", "On my way"))

    def test_a_file_for_the_person(self):
        preview.save_as("a.txt", "a", on_result=self.answer)
        self.assertEqual(self.heard, [(False, "cancelled")])       # nobody to ask
        preview.save_copy("no-such-file.bin", on_result=self.answer)
        self.assertEqual(self.heard[-1], (False, "not_found"))

    def test_a_download_that_is_not_a_web_address(self):
        preview.DownloadsAPI().start("ftp://example.com/a", on_result=self.answer)
        self.assertEqual(self.heard, [(False, "invalid")])

    def test_a_recording_is_a_file_that_plays(self):
        from apkpy_lib import ui
        recorder = preview.RecorderAPI()
        self.assertEqual(recorder.stop(), "")
        self.assertEqual(recorder.seconds(), "0")
        granted = set(ui.permissions._granted)
        try:
            recorder.start(on_result=self.answer)
            self.assertEqual(self.heard, [(True, "ok")])
            self.assertIs(recorder.is_recording(), True)
            recorder.start(on_result=self.answer)
            self.assertEqual(self.heard[-1], (False, "busy"))
            time.sleep(0.35)
            path = recorder.stop()
        finally:
            ui.permissions._granted.clear()
            ui.permissions._granted.update(granted)
        self.assertIs(recorder.is_recording(), False)
        self.assertTrue(path.endswith(".wav"), path)
        try:
            with wave.open(path, "rb") as sound:
                self.assertEqual(sound.getframerate(), recorder.RATE)
                self.assertGreater(sound.getnframes(), recorder.RATE * 0.25)
        finally:
            os.remove(path)

    def test_a_document(self):
        printing = preview.PrintingAPI()
        printing.text("a < b", name="Sums", on_result=self.answer)
        self.assertEqual(self.heard, [(True, "ok")])
        self.assertEqual(printing.last[0], "Sums")
        self.assertIn("a &lt; b", printing.last[1])

    def test_what_came_in(self):
        incoming = preview.IncomingAPI()
        self.assertEqual(incoming.link(), "")
        incoming.links("notes", preview="notes://open/42")
        incoming.shares("text", preview="Buy milk")
        incoming.shares("image", preview="photo.jpg")
        self.assertEqual((incoming.link(), incoming.text(), incoming.file()),
                         ("notes://open/42", "Buy milk", "photo.jpg"))
        self.assertEqual(incoming.clear(), "ok")
        self.assertEqual((incoming.link(), incoming.text(), incoming.file()), ("", "", ""))
        with self.assertRaises(ApkpyError) as caught:
            incoming.links("tel")
        self.assertEqual(caught.exception.code, "U2048")

    def test_a_call_that_does_not_exist_is_said_as_the_build_says_it(self):
        with self.assertRaises(ApkpyError) as caught:
            preview.speech.speak("hi")
        error = caught.exception
        self.assertEqual((error.code, str(error)), ("U2048", "speech has no speak()"))
        self.assertTrue(any("Did you mean speech.say(" in hint for hint in error.suggestions))
        self.assertIn("speech has no speak()", _error('speech.speak("hi")'))
        # Code that walks an app's names asks hasattr() of everything in it.
        self.assertFalse(hasattr(preview.haptics, "widget"))
        self.assertTrue(hasattr(preview.haptics, "tap"))
        with self.assertRaises(AttributeError):
            preview.haptics._private

    def test_a_job_body_is_refused_with_the_builds_words(self):
        for call in (lambda: preview.haptics.tap(), lambda: preview.phone.dial("1"),
                     lambda: preview.speech.is_speaking(),
                     lambda: preview.save_as("a", "b")):
            with job_rules.running_job():
                with self.assertRaises(ApkpyError) as caught:
                    call()
            self.assertEqual(caught.exception.code, "J7004")
        self.assertIn("haptics.tap() cannot run inside a background job",
                      self._refusal(lambda: preview.haptics.tap()))

    def _refusal(self, call):
        with job_rules.running_job():
            try:
                call()
            except ApkpyError as error:
                return str(error)
        return ""


class OnTheDeskInThePreviewer(unittest.TestCase):
    """With the window open, each call is something a person can see and
    answer."""

    APP = ('home = Screen(id="home")\n'
           'out = label("", id="out", screen=home)\n'
           'HEARD = []\n'
           'def answered(ok, value):\n'
           '    HEARD.append((ok, value))\n')

    def setUp(self):
        self._browser = os.environ.get("APKPY_PREVIEW_NO_BROWSER")
        os.environ["APKPY_PREVIEW_NO_BROWSER"] = "1"

    def tearDown(self):
        kit_surfaces.close_all()
        preview._LIT.clear()
        if self._browser is None:
            os.environ.pop("APKPY_PREVIEW_NO_BROWSER", None)
        else:
            os.environ["APKPY_PREVIEW_NO_BROWSER"] = self._browser

    def test_handing_over_is_a_sheet_and_the_app_is_back_when_it_closes(self):
        with Previewed(self.APP, "") as p:
            self.assertEqual(p.ns["phone"].dial("+351 912 345 678"), "ok")
            p.settle(0.5)
            sheet = kit_surfaces.current()
            self.assertEqual((sheet.kind, sheet.app_name, sheet.title),
                             ("dial", "Phone", "+351 912 345 678"))
            # It stands on the bottom edge of the app, as wide as the app.
            self.assertEqual(sheet.win.winfo_rooty() + sheet.win.winfo_height(),
                             sheet.root_y + sheet.root_h)
            self.assertEqual(sheet.win.winfo_width(), sheet.root_w)
            sheet.close()
            p.settle(0.5)
            self.assertIsNone(kit_surfaces.current())

    def test_what_the_other_app_was_given_is_on_the_sheet(self):
        with Previewed(self.APP, "") as p:
            p.ns["calendar"].add_event("Dentist", "2026-11-03 15:30", location="Rua Augusta 12")
            p.settle(0.4)
            sheet = kit_surfaces.current()
            self.assertEqual(sheet.title, "Dentist")
            self.assertEqual([icon for icon, _text in sheet.rows], ["schedule", "place"])
            self.assertIn("15:30 – 16:30", sheet.rows[0][1])
            p.ns["phone"].sms("912 345 678", "On my way")
            p.settle(0.5)
            self.assertEqual(kit_surfaces.current().quote, "On my way")
            self.assertEqual(len(kit_surfaces._open), 1)       # one app in front at a time

    def test_a_page_inside_the_app_answers_when_it_is_closed(self):
        with Previewed(self.APP, "") as p:
            p.ns["browser"].show("https://example.com/terms", title="Terms",
                                 on_result=p.ns["answered"])
            p.settle(0.4)
            self.assertEqual(p.ns["HEARD"], [])
            kit_surfaces.current().close()
            p.settle(0.5)
            self.assertEqual(p.ns["HEARD"], [(True, "https://example.com/terms")])

    def test_dictation_is_typed(self):
        with Previewed(self.APP, "") as p:
            p.ns["speech"].listen(prompt="Say a city", on_result=p.ns["answered"])
            p.settle(0.4)
            sheet = kit_surfaces.current()
            self.assertEqual((sheet.kind, sheet.title), ("listen", "Say a city"))
            self.assertIn("mic", preview.status_glyphs())
            sheet.entry.insert(0, "  Lisbon ")
            sheet.finish()
            p.settle(0.5)
            self.assertEqual(p.ns["HEARD"], [(True, "Lisbon")])
            self.assertNotIn("mic", preview.status_glyphs())

            p.ns["speech"].listen(on_result=p.ns["answered"])
            p.settle(0.4)
            kit_surfaces.current().close()
            p.settle(0.5)
            self.assertEqual(p.ns["HEARD"][-1], (False, "cancelled"))

    def test_a_voice_is_a_caption_for_as_long_as_it_would_speak(self):
        with Previewed(self.APP, "") as p:
            speech = preview.SpeechAPI()
            speech.say("One two three four five six seven eight", on_result=p.ns["answered"])
            p.settle(0.3)
            self.assertIs(speech.is_speaking(), True)
            self.assertEqual(kit_surfaces._captions[0].apkpy_caption,
                             "One two three four five six seven eight")
            speech.say("Next", on_result=p.ns["answered"])
            p.settle(0.2)
            self.assertEqual(p.ns["HEARD"], [(False, "stopped")])
            self.assertEqual(len(kit_surfaces._captions), 1)
            p.settle(1.0)
            self.assertEqual(p.ns["HEARD"][-1], (True, "ok"))
            self.assertIs(speech.is_speaking(), False)

    def test_the_microphone_is_asked_for_the_way_android_asks(self):
        from apkpy_lib import ui
        granted = set(ui.permissions._granted)
        ui.permissions._granted.discard("RECORD_AUDIO")
        recorder = preview.RecorderAPI()
        recorder._begin = lambda: setattr(recorder, "_since", time.monotonic())
        recorder._close = lambda: setattr(recorder, "_since", None)
        try:
            with Previewed(self.APP, "") as p:
                recorder.start(on_result=p.ns["answered"])
                p.settle(0.4)
                sheet = kit_surfaces.current()
                self.assertEqual(sheet.kind, "permission")
                self.assertEqual([value for _label, value in sheet.choices],
                                 ["always", "once", "deny"])
                sheet.choose("deny")
                p.settle(0.5)
                self.assertEqual(p.ns["HEARD"], [(False, "permission_denied")])
                self.assertIs(recorder.is_recording(), False)

                recorder.start(on_result=p.ns["answered"])
                p.settle(0.4)
                kit_surfaces.current().choose("once")
                p.settle(0.5)
                self.assertEqual(p.ns["HEARD"][-1], (True, "ok"))
                self.assertIn("mic", preview.status_glyphs())
                # "Only this time" is not remembered.
                self.assertIs(ui.permissions.has("RECORD_AUDIO"), False)
                recorder._since = None
        finally:
            ui.permissions._granted.clear()
            ui.permissions._granted.update(granted)

    def test_the_motor_shows_in_the_strip_and_goes_out(self):
        with Previewed(self.APP, "") as p:
            preview.haptics.tap()
            self.assertIn("vibrate", preview.status_glyphs())
            p.settle(0.6)
            self.assertNotIn("vibrate", preview.status_glyphs())


if __name__ == "__main__":
    unittest.main()
