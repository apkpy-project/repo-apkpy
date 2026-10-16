# -*- coding: utf-8 -*-
"""What the phone's screen does while one of the app's screens is on show.

    display.keep_on(True)       display.brightness(0.9)
    display.immersive(True)     display.orientation("landscape")
    Screen(id="player", orientation="landscape")
    run(start_screen=home, orientation="portrait")

Four calls of the same table as the rest of the kit, and a word on a screen
and on run() that goes into the manifest. What these tests hold: the phone and
the desk read a level and a way up from the same text in the same way, each
call is one line of the app, what cannot be built is refused in the same words
on both sides, what a screen asks for is that screen's -- and on the desk each
of the four can be seen: two glyphs in the strip, the strip gone, the window
on its side.
"""

import io
import os
import shutil
import subprocess
import tempfile
import unittest

import apkpy_lib
from apkpy_lib import job_rules, ui
from apkpy_lib import kit_rules as rules
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import kit
from apkpy_lib.diagnostics import ApkpyError
from apkpy_lib.features import kit as preview

from test_data_rules import TOOLING
from test_kit import HEAD, TAIL, _built, _error, _java
from test_real_screens import Previewed

# text -> display.brightness(): the level, -1 for the phone's own, -2 for neither
LEVELS = [
    ("0", 0.0), ("1", 1.0), ("0.9", 0.9), (" 0.5 ", 0.5), ("1.0", 1.0), ("-0", 0.0),
    ("auto", -1.0), ("AUTO", -1.0), (" Auto ", -1.0),
    ("90", -2.0), ("1.01", -2.0), ("-0.1", -2.0), ("-1", -2.0), ("", -2.0),
    ("bright", -2.0), ("True", -2.0), ("automatic", -2.0), ("0,5", -2.0),
]
# text -> display.orientation(): one of the three, or "" for none of them
WAYS = [
    ("portrait", "portrait"), ("landscape", "landscape"), ("auto", "auto"),
    ("Portrait", "portrait"), (" LANDSCAPE ", "landscape"), ("Auto", "auto"),
    ("sideways", ""), ("", ""), ("portrait ", "portrait"), ("land scape", ""),
    ("vertical", ""), ("PORTRAİT", ""),      # a dotted capital I is no I
]


def _forget():
    apkpy_lib.display._asked = {}
    preview._LIT.pop("awake", None)
    preview._LIT.pop("brightness", None)
    ui._app_orientation = None


class TheRules(unittest.TestCase):
    """What a level and a way up are read as."""

    def test_a_level_is_from_nothing_to_one_or_the_phones_own(self):
        for text, wanted in LEVELS:
            self.assertEqual(rules.display_brightness(text), wanted, repr(text))
        self.assertEqual(rules.display_brightness(0.25), 0.25)
        self.assertEqual(rules.display_brightness(1), 1.0)
        self.assertEqual(rules.display_brightness(True), rules.BRIGHTNESS_INVALID)
        self.assertEqual(rules.display_brightness(None), rules.BRIGHTNESS_INVALID)

    def test_a_number_outside_is_not_brought_inside(self):
        # 90 is somebody who meant 0.9: full brightness is not the answer.
        self.assertEqual(rules.display_brightness("90"), rules.BRIGHTNESS_INVALID)
        self.assertEqual(rules.display_brightness("auto"), rules.BRIGHTNESS_OWN)

    def test_a_way_up_is_one_of_three_words(self):
        for text, wanted in WAYS:
            self.assertEqual(rules.display_orientation(text), wanted, repr(text))
            self.assertIn(wanted, rules.ORIENTATIONS + ("",))
        self.assertEqual(rules.display_orientation(None), "")

    @unittest.skipUnless(TOOLING[0], "no JDK on this machine")
    def test_the_two_languages_agree(self):
        def written(text):
            return '"%s"' % text.replace("İ", "\\u0130")

        lines = []
        for index, (text, _wanted) in enumerate(LEVELS):
            lines.append('System.out.println("l%d|" + ApkpyKitRules.displayBrightness(%s));'
                         % (index, written(text)))
        for index, (text, _wanted) in enumerate(WAYS):
            lines.append('System.out.println("w%d|" + ApkpyKitRules.displayOrientation(%s));'
                         % (index, written(text)))
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-display-rules-")
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
            ran = subprocess.run([java_bin, "-cp", work, "Harness"], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        answers = dict(line.split("|", 1) for line in ran.stdout.splitlines())
        self.assertEqual(len(answers), len(LEVELS) + len(WAYS))
        for index, (text, wanted) in enumerate(LEVELS):
            self.assertEqual(float(answers["l%d" % index]), wanted, repr(text))
        for index, (text, wanted) in enumerate(WAYS):
            self.assertEqual(answers["w%d" % index], wanted, repr(text))


class WhatIsBuilt(unittest.TestCase):

    BODY = ('display.keep_on(True)\n'
            'display.brightness(0.9)\n'
            'display.immersive()\n'
            'word = display.orientation("landscape")\n'
            'out.set_value(word)')

    def test_each_call_is_one_line_of_the_class(self):
        java = _java(self.BODY)
        for line in ("return ApkpyDisplay.keepOn(this, on);",
                     "return ApkpyDisplay.brightness(this, level);",
                     "return ApkpyDisplay.immersive(this, on);",
                     "return ApkpyDisplay.orientation(this, kind);"):
            self.assertIn(line, java)
        self.assertIn("_apkpyNative_display_keep_on(String.valueOf(true))", java)
        self.assertIn("_apkpyNative_display_brightness(String.valueOf(0.9))", java)
        # Left out, it is on: what the table says immersive() means.
        self.assertIn('_apkpyNative_display_immersive(String.valueOf("true"))', java)

    def test_what_a_switch_hands_over_is_what_keep_on_takes(self):
        java = _java('display.keep_on(value)', top='value = "true"\n')
        self.assertIn("_apkpyNative_display_keep_on(String.valueOf(value))", java)

    def test_only_what_it_needs_goes_into_the_app(self):
        files = _built(self.BODY)
        self.assertIn("java/ApkpyDisplay.java", files)
        self.assertIn("java/ApkpyKitRules.java", files)
        for other in ("ApkpyTimers", "ApkpyNetwork", "ApkpyHaptics", "ApkpyKitActivity"):
            self.assertNotIn("java/%s.java" % other, files)
        # The screen is the app's own to keep on, dim and turn: nobody is asked.
        self.assertNotIn("uses-permission", files["AndroidManifest.xml"])
        self.assertNotIn("WAKE_LOCK", files["AndroidManifest.xml"])

    def test_an_app_with_none_of_it_has_none_of_it(self):
        files = _built('out.set_value("x")')
        self.assertFalse([name for name in files if "ApkpyDisplay" in name])
        self.assertNotIn("screenOrientation", files["AndroidManifest.xml"])

    def test_a_name_the_app_made_its_own_is_left_alone(self):
        files = _built('display.set_value("12")',
                       top='display = label("0", id="display", screen=home)\n')
        self.assertNotIn("java/ApkpyDisplay.java", files)

    def test_the_class_is_written_for_the_app(self):
        source = _built(self.BODY)["java/ApkpyDisplay.java"]
        self.assertNotIn("__", source.replace("__PACKAGE__", "") if "__PACKAGE__" in source else source)
        self.assertTrue(source.startswith("package "))
        # A window's flags, never a wake lock: nothing to hold and forget.
        for forbidden in ("PowerManager", "WakeLock", "Settings.System"):
            self.assertNotIn(forbidden, source)


class WhichWayUpIsBuilt(unittest.TestCase):
    """Screen(orientation=) and run(orientation=) are a word in the manifest."""

    APP = ('from apkpy_lib import *\n'
           'home = Screen(id="home"%s)\n'
           'player = Screen(id="player"%s)\n'
           'free = Screen(id="free"%s)\n'
           'label("Home", screen=home)\n'
           'label("Player", screen=player)\n'
           'label("Free", screen=free)\n'
           'run(start_screen=home%s)\n')

    def _activities(self, home="", player="", free="", app=""):
        files = translate_python_to_android(self.APP % (home, player, free, app))
        if "error.txt" in files:
            raise AssertionError(files["error.txt"][:900])
        lines = [line.strip() for line in files["AndroidManifest.xml"].splitlines()
                 if "<activity" in line]
        return {name: next(line for line in lines if ".Screen_%sActivity" % name in line)
                for name in ("home", "player", "free")}

    def test_nothing_said_and_nothing_is_written(self):
        for line in self._activities().values():
            self.assertNotIn("screenOrientation", line)

    def test_run_says_it_for_every_screen(self):
        found = self._activities(app=', orientation="portrait"')
        for line in found.values():
            self.assertIn('android:screenOrientation="portrait"', line)
        self.assertIn('android:exported="true"', found["home"])

    def test_a_screen_says_it_for_itself_and_wins(self):
        found = self._activities(player=', orientation="landscape"',
                                 free=', orientation="auto"', app=', orientation="portrait"')
        self.assertIn('android:screenOrientation="portrait"', found["home"])
        # Either way round: a phone lying on its other side is still lying down.
        self.assertIn('android:screenOrientation="sensorLandscape"', found["player"])
        # Turning with the phone is what Android does with a screen that asks nothing.
        self.assertNotIn("screenOrientation", found["free"])

    def test_one_screen_alone(self):
        found = self._activities(player=', orientation="landscape"')
        self.assertIn("sensorLandscape", found["player"])
        self.assertNotIn("screenOrientation", found["home"])

    def test_the_rest_of_the_manifest_is_as_it_was(self):
        plain = translate_python_to_android(self.APP % ("", "", "", ""))
        held = translate_python_to_android(self.APP % ("", "", "", ', orientation="portrait"'))
        self.assertEqual(sorted(plain), sorted(held))
        self.assertEqual(held["AndroidManifest.xml"].replace(
            ' android:screenOrientation="portrait"', ""), plain["AndroidManifest.xml"])
        for name in plain:
            if name != "AndroidManifest.xml":
                self.assertEqual(plain[name], held[name], name)


class WhatStopsTheBuild(unittest.TestCase):

    def _stops(self, body, *words, top="", code="U2048"):
        text = _error(body, top)
        self.assertIn(code, text)
        for word in words:
            self.assertIn(word, text)
        return text

    def _app_stops(self, source, *words):
        text = " ".join(translate_python_to_android(source)["error.txt"].split())
        self.assertIn("U2048", text)
        for word in words:
            self.assertIn(word, text)
        return text

    def test_a_way_up_that_is_none_of_the_three(self):
        text = self._stops('display.orientation("sideways")',
                           "display.orientation(): there is no orientation 'sideways'",
                           'One of: "auto", "portrait", "landscape".')
        self.assertIn("/guides/display/", text)

    def test_a_level_that_is_not_one(self):
        self._stops('display.brightness(90)',
                    'display.brightness(): level= is from 0 to 1 or "auto", got \'90\'',
                    "For 90%, write 0.9.")
        self._stops('display.brightness(-1)', "got '-1'")
        self._stops('display.brightness("bright")', "got 'bright'", '"auto" gives the level back')
        self._stops('display.brightness(True)', "got 'True'")
        self._stops('display.brightness(None)', "level= is text, got None")

    def test_what_is_worked_out_while_the_app_runs_is_passed_on(self):
        java = _java('display.brightness(level)\ndisplay.orientation(way)',
                     top='level = "0.4"\nway = "auto"\n')
        self.assertIn("_apkpyNative_display_brightness(String.valueOf(level))", java)

    def test_what_is_written_wrong(self):
        self._stops('display.brightness()', "display.brightness() needs level")
        self._stops('display.orientation()', "display.orientation() needs kind")
        self._stops('display.keep_on("yes")', "display.keep_on(): on= is True or False")
        self._stops('display.keep_on(True, True)', "at most 1 argument")
        self._stops('display.immersive(on_result=answered)', "display.immersive() has no on_result=",
                    "answers at once")
        self._stops('display.keep_on(on=True, level=1)', "display.keep_on() has no level=")

    def test_a_call_that_does_not_exist(self):
        self._stops('display.rotate("landscape")', "display has no rotate()",
                    "display has: keep_on(), brightness(), immersive(), orientation().")
        self._stops('display.keep_awake()', "display has no keep_awake()", "display.keep_on(on=True)")
        self._stops('display.fullscreen()', "display has no fullscreen()")

    def test_it_is_asked_by_a_function_not_by_the_top_of_the_file(self):
        for line, extra in (('display.keep_on(True)', ""),
                            ('display.immersive()', ""),
                            ('display.brightness(1)', ""),
                            ('display.orientation("portrait")',
                             'run(start_screen=home, orientation="portrait")')):
            source = HEAD + line + '\n\ndef go():\n    out.set_value("x")\n' + TAIL
            text = self._app_stops(
                source, "%s at the top of the file runs before there is a screen"
                % (line.split("(")[0] + "()"),
                "belongs to the screen that is on show when it is asked",
                "lifecycle(home, on_mount=opened)")
            # Only the way up has a word for the whole app.
            if extra:
                self.assertIn(extra, text)
            else:
                self.assertNotIn("run(start_screen=home, orientation=", text)

    def test_asked_as_the_screen_opens(self):
        source = (HEAD + 'def opened():\n    display.keep_on(True)\n\n'
                  'lifecycle(home, on_mount=opened)\n\ndef go():\n    out.set_value("x")\n' + TAIL)
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files)
        self.assertIn("pythonCallback_opened();", files["java/Screen_homeActivity.java"])

    def test_inside_a_background_job(self):
        source = (HEAD +
                  'def work(job):\n'
                  '    display.keep_on(True)\n\n'
                  'sync = background_job("sync", run=work)\n'
                  'def go():\n'
                  '    sync.enqueue()\n' + TAIL)
        text = " ".join(translate_python_to_android(source).get("error.txt", "").split())
        self.assertIn("J7004", text)
        self.assertIn("display.keep_on() cannot run inside a background job", text)

    def test_the_word_on_a_screen_and_on_run(self):
        app = WhichWayUpIsBuilt.APP
        text = self._app_stops(app % (', orientation="sideways"', "", "", ""),
                               "Screen(orientation=): there is no orientation 'sideways'",
                               'One of: "auto", "portrait", "landscape".')
        self.assertIn("/guides/display/", text)
        self._app_stops(app % ("", "", "", ', orientation="flat"'),
                        "run(orientation=): there is no orientation 'flat'")
        text = self._app_stops('WAY = "portrait"\n' + app % (", orientation=WAY", "", "", ""),
                               "Screen(orientation=) has to be text written in the source",
                               "it never runs it", 'display.orientation("landscape")')
        self.assertIn("/guides/display/", text)
        # None is nothing said.
        self.assertNotIn("error.txt", translate_python_to_android(
            app % (", orientation=None", "", "", ", orientation=None")))


class OnTheDesk(unittest.TestCase):
    """With no window: what the calls answer, and the build's own refusals."""

    def setUp(self):
        _forget()

    tearDown = setUp

    def _said(self, call):
        with self.assertRaises(ApkpyError) as raised:
            call()
        self.assertEqual(raised.exception.code, "U2048")
        return str(raised.exception)

    def test_what_each_answers(self):
        display = apkpy_lib.display
        self.assertEqual(display.keep_on(True), "ok")
        self.assertEqual(display.keep_on(), "ok")
        self.assertEqual(display.brightness(0.9), "ok")
        self.assertEqual(display.brightness("auto"), "ok")
        self.assertEqual(display.brightness(90), "invalid")
        self.assertEqual(display.brightness("bright"), "invalid")
        self.assertEqual(display.immersive(False), "ok")
        self.assertEqual(display.orientation("landscape"), "ok")
        self.assertEqual(display.orientation("sideways"), "invalid")
        for word in ("ok", "invalid"):
            self.assertIn(word, display.reasons)

    def test_what_is_kept_is_what_was_last_asked_and_a_wrong_one_changes_nothing(self):
        display = apkpy_lib.display
        display.keep_on("true")             # what a switch hands over
        display.brightness("0.4")
        display.brightness(7)
        display.orientation("Landscape")
        display.orientation("up")
        asked = display._for(None)
        self.assertEqual((asked.keep_on, asked.brightness, asked.immersive, asked.orientation),
                         (True, 0.4, False, "landscape"))
        display.keep_on("false")
        display.brightness("auto")
        display.orientation("auto")
        asked = display._for(None)
        self.assertEqual((asked.keep_on, asked.brightness, asked.orientation),
                         (False, rules.BRIGHTNESS_OWN, "auto"))

    def test_a_screen_that_never_asked_has_asked_for_nothing(self):
        asked = apkpy_lib.display._for(object())
        self.assertEqual((asked.keep_on, asked.brightness, asked.immersive, asked.orientation),
                         (False, rules.BRIGHTNESS_OWN, False, ""))

    def test_the_words_are_the_builds(self):
        cases = [
            (lambda: apkpy_lib.display.rotate("landscape"),
             'display.rotate("landscape")', "display has no rotate()"),
            (lambda: apkpy_lib.display.keep_awake(),
             'display.keep_awake()', "display has no keep_awake()"),
        ]
        for call, body, words in cases:
            self.assertIn(words, self._said(call))
            self.assertIn(words, _error(body))

    def test_the_word_on_a_screen_is_refused_as_the_build_refuses_it(self):
        words = "Screen(orientation=): there is no orientation 'sideways'"
        self.assertIn(words, self._said(lambda: ui.Screen(id="lost", orientation="sideways")))
        ui._ALL_SCREENS[:] = [screen for screen in ui._ALL_SCREENS if screen.id != "lost"]
        self.assertIn(words, " ".join(translate_python_to_android(
            WhichWayUpIsBuilt.APP % (', orientation="sideways"', "", "", ""))["error.txt"].split()))
        self.assertIn("run(orientation=): there is no orientation 'flat'",
                      self._said(lambda: ui._orientation_written("flat", "run")))
        self.assertIsNone(ui._orientation_written(None, "run"))
        self.assertEqual(ui._orientation_written(" Portrait ", "run"), "portrait")
        self.assertIn("there is no orientation 3", self._said(
            lambda: ui._orientation_written(3, "Screen")))

    def test_the_top_of_the_file_is_refused_as_the_build_refuses_it(self):
        for line in ('display.keep_on(True)', 'display.brightness(1)',
                     'display.immersive(True)', 'display.orientation("portrait")'):
            with self.assertRaises(ApkpyError) as raised:
                exec('from apkpy_lib import display\n' + line + '\n', {})
            self.assertEqual(raised.exception.code, "U2048")
            self.assertIn("%s at the top of the file runs before there is a screen"
                          % (line.split("(")[0] + "()"), str(raised.exception))
        self.assertEqual(apkpy_lib.display._asked, {})

    def test_a_job_body_is_refused_with_the_builds_words(self):
        display = apkpy_lib.display
        with job_rules.running_job():
            for call in (lambda: display.keep_on(True), lambda: display.brightness(1),
                         lambda: display.immersive(True),
                         lambda: display.orientation("portrait")):
                with self.assertRaises(ApkpyError) as raised:
                    call()
                self.assertEqual(raised.exception.code, "J7004")
                self.assertIn("cannot run inside a background job", str(raised.exception))

    def test_every_error_sends_the_reader_to_its_own_page(self):
        with self.assertRaises(ApkpyError) as raised:
            apkpy_lib.display.rotate()
        self.assertEqual(raised.exception.docs, rules.DOCS_OF["display"])
        for family in ("timer", "network", "display"):
            self.assertEqual(rules.docs_for("%s.x() has no y=" % family), rules.DOCS_OF[family])
        self.assertEqual(rules.docs_for("haptics.tap() takes no arguments"), rules.DOCS)
        self.assertEqual(rules.docs_for("ads.banner(): position="), rules.DOCS_OUTSIDE)


class _Over:
    def __init__(self, x):
        self.x = x


class InThePreviewer(unittest.TestCase):
    """The window open: each of the four can be seen."""

    APP = ('home = Screen(id="home")\n'
           'detail = Screen(id="detail")\n'
           'player = Screen(id="player", orientation="landscape")\n'
           'out = label("Home", id="out", screen=home)\n'
           'label("Detail", id="title", screen=detail)\n'
           'label("Player", id="film", screen=player)\n'
           'def awake(on):\n'
           '    return display.keep_on(on)\n'
           'def level(value):\n'
           '    return display.brightness(value)\n'
           'def bars(hidden):\n'
           '    return display.immersive(hidden)\n'
           'def way(kind):\n'
           '    return display.orientation(kind)\n')

    def setUp(self):
        _forget()

    tearDown = setUp

    def _lit(self):
        return [name for name in ui._lit_status_glyphs() if name in ("awake", "brightness")]

    def _over(self, glyph):
        order = ui._lit_status_glyphs() + ui._status_glyph_order()
        return _Over(order.index(glyph) * ui._STATUS_GLYPH_SIZE + ui._STATUS_GLYPH_SIZE // 2)

    def test_a_cup_while_the_screen_keeps_the_phone_on(self):
        with Previewed(self.APP, "") as shown:
            self.assertEqual(self._lit(), [])
            self.assertEqual(shown.ns["awake"](True), "ok")
            self.assertEqual(self._lit(), ["awake"])
            self.assertEqual(int(shown.app._status_icons.cget("width")),
                             4 * ui._STATUS_GLYPH_SIZE)
            self.assertEqual(shown.ns["awake"](False), "ok")
            self.assertEqual(self._lit(), [])

    def test_it_is_the_screens_and_another_one_has_none_of_it(self):
        with Previewed(self.APP, "") as shown:
            shown.ns["awake"](True)
            shown.ns["level"](1)
            shown.app.render_screen(shown.ns["detail"])
            shown.settle(0.1)
            self.assertEqual(self._lit(), [])
            # Back: the first screen was under the second all along.
            shown.app.go_back()
            shown.settle(0.1)
            self.assertEqual(self._lit(), ["awake", "brightness"])

    def test_a_screen_left_with_back_is_closed_and_what_it_asked_goes_with_it(self):
        with Previewed(self.APP, "") as shown:
            shown.app.render_screen(shown.ns["detail"])
            shown.settle(0.1)
            shown.ns["awake"](True)
            self.assertEqual(self._lit(), ["awake"])
            shown.app.go_back()
            shown.settle(0.1)
            shown.app.render_screen(shown.ns["detail"])
            shown.settle(0.1)
            self.assertEqual(self._lit(), [])

    def test_a_sun_for_the_level_and_each_glyph_says_what_it_is(self):
        with Previewed(self.APP, "") as shown:
            app = shown.app
            self.assertEqual(shown.ns["level"](0.9), "ok")
            shown.ns["awake"](True)
            self.assertEqual(self._lit(), ["awake", "brightness"])
            app._status_connection_hover(self._over("brightness"))
            self.assertEqual(app._status_hint.cget("text"), "Brightness 90% on this screen")
            self.assertEqual(app._status_icons.cget("cursor"), "")
            app._status_connection_hover(self._over("awake"))
            self.assertEqual(app._status_hint.cget("text"), "This screen keeps the phone on")
            app._status_connection_hover(self._over("battery"))
            self.assertIsNone(app._status_hint)
            self.assertEqual(shown.ns["level"](90), "invalid")
            self.assertEqual(self._lit(), ["awake", "brightness"])
            self.assertEqual(shown.ns["level"]("auto"), "ok")
            self.assertEqual(self._lit(), ["awake"])

    def test_the_strip_goes_and_the_screen_has_the_whole_window(self):
        with Previewed(self.APP, "") as shown:
            app = shown.app
            self.assertEqual(app._status_frame.winfo_manager(), "place")
            before = shown.widget("out").winfo_rooty()
            self.assertEqual(shown.ns["bars"](True), "ok")
            shown.settle(0.15)
            self.assertEqual(app._status_frame.winfo_manager(), "")
            self.assertEqual(before - shown.widget("out").winfo_rooty(), ui._STATUS_STRIP_HEIGHT)
            # Another screen has its strip; back, and this one still has none.
            app.render_screen(shown.ns["detail"])
            shown.settle(0.1)
            self.assertEqual(app._status_frame.winfo_manager(), "place")
            app.go_back()
            shown.settle(0.1)
            self.assertEqual(app._status_frame.winfo_manager(), "")
            self.assertEqual(shown.ns["bars"](False), "ok")
            shown.settle(0.15)
            self.assertEqual(app._status_frame.winfo_manager(), "place")
            self.assertEqual(shown.widget("out").winfo_rooty(), before)

    def test_a_screen_that_lies_down_is_shown_lying_down(self):
        with Previewed(self.APP, "") as shown:
            app = shown.app
            self.assertEqual(app._shape, (411, 914))
            app.render_screen(shown.ns["player"])
            shown.settle(0.2)
            self.assertEqual(app._shape, (914, 411))
            self.assertEqual((app.root.winfo_width(), app.root.winfo_height()), (914, 411))
            self.assertEqual(ui._style_viewport, (914, 411))
            app.go_back()
            shown.settle(0.2)
            self.assertEqual(app._shape, (411, 914))
            self.assertEqual(ui._style_viewport[0], 411)

    def test_asked_while_it_runs_the_screen_is_drawn_again_once_the_call_is_over(self):
        with Previewed(self.APP, "") as shown:
            app = shown.app
            drawn = []
            render = app.render_screen
            app.render_screen = lambda screen, *more, **kept: (drawn.append(screen.id),
                                                               render(screen, *more, **kept))[1]
            self.assertEqual(shown.ns["way"]("landscape"), "ok")
            self.assertEqual(drawn, [])                     # not inside the call
            self.assertEqual(app._shape, (914, 411))
            shown.settle(0.2)
            self.assertEqual(drawn, ["home"])
            self.assertEqual(shown.ns["way"]("landscape"), "ok")
            shown.settle(0.2)
            self.assertEqual(drawn, ["home"])               # already lying down
            self.assertEqual(shown.ns["way"]("portrait"), "ok")
            shown.settle(0.2)
            self.assertEqual((app._shape, drawn), ((411, 914), ["home", "home"]))

    def test_what_run_says_holds_every_screen_that_says_nothing(self):
        with Previewed(self.APP, "") as shown:
            app = shown.app
            ui._app_orientation = "landscape"
            self.assertEqual(app._way_up(shown.ns["home"]), ("landscape", True))
            self.assertEqual(app._way_up(shown.ns["player"]), ("landscape", True))
            ui._app_orientation = "portrait"
            self.assertEqual(app._way_up(shown.ns["home"]), ("portrait", True))
            self.assertEqual(app._way_up(shown.ns["player"]), ("landscape", True))
            # What the screen asks while it runs wins over both.
            shown.ns["way"]("auto")
            self.assertEqual(app._way_up(shown.ns["home"]), ("portrait", False))

    def test_the_phone_is_the_previewers_to_turn(self):
        with Previewed(self.APP, "") as shown:
            app = shown.app
            self.assertEqual(app._way_up(shown.ns["home"]), ("portrait", False))
            self.assertEqual(app._turn_device(), "break")
            shown.settle(0.2)
            self.assertEqual(app._shape, (914, 411))
            self.assertEqual(app._way_up(shown.ns["home"]), ("landscape", False))
            self.assertEqual(app._turn_device(), "break")
            shown.settle(0.2)
            self.assertEqual(app._shape, (411, 914))

    def test_a_screen_that_is_held_stays_and_says_so(self):
        with Previewed(self.APP, "") as shown:
            app = shown.app
            ui._app_orientation = "portrait"
            app._turn_device()
            shown.settle(0.1)
            self.assertEqual(app._shape, (411, 914))
            self.assertEqual(app._status_hint.cget("text"), "This screen stays in portrait")
            # The phone is on its side all the same: a screen that turns is shown so.
            shown.ns["way"]("auto")
            shown.settle(0.2)
            self.assertEqual(app._shape, (914, 411))

    def test_on_a_tablet_nothing_is_held(self):
        # Android 16 turns every screen with the device from 600dp up.
        with Previewed(self.APP, "") as shown:
            app = shown.app
            app._upright = (800, 1100)
            self.assertEqual(app._way_up(shown.ns["player"]), ("portrait", False))
            app._upright = (rules.LARGE_SCREEN - 1, 1100)
            self.assertEqual(app._way_up(shown.ns["player"]), ("landscape", True))

    def test_a_window_that_is_the_persons_to_shape_is_left_alone(self):
        with Previewed(self.APP, "") as shown:
            app = shown.app
            app._upright = None
            self.assertFalse(app._shape_for(shown.ns["player"]))
            self.assertEqual(app._turn_device(), "break")
            self.assertEqual(app._shape, (411, 914))


if __name__ == "__main__":
    unittest.main()
