# -*- coding: utf-8 -*-
"""A function of the app run later, or again and again.

    timer.after(2, hide_banner)     timer.every(1, tick)
    timer.cancel(tick)              if timer.running(tick): ...

Four calls of the same table as the rest of the kit. A timer is known by the
function it calls and belongs to the screen it was started on. What these
tests hold: the phone and the desk read a time alike and keep the same grid
of moments, a function crosses to the phone as its name and every screen can
be asked for it, what cannot be built is refused in the same words on both
sides, and a screen that is not on show runs nothing and misses nothing.
"""

import io
import os
import shutil
import subprocess
import tempfile
import unittest

import apkpy_lib
from apkpy_lib import job_rules
from apkpy_lib import kit_rules as rules
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import kit
from apkpy_lib.diagnostics import ApkpyError
from apkpy_lib.features import kit as preview

from test_data_rules import TOOLING
from test_kit import HEAD, TAIL, _built, _error, _java, needs_sdk
from test_real_screens import Previewed

TICK = ('def tick():\n'
        '    out.set_value("tick")\n'
        '\n'
        'def hide():\n'
        '    out.set_value("")\n'
        '\n')

# what is written for seconds -> (as after() reads it, as every() reads it)
TIMES = [
    ("2", 2000, 2000), ("0.4", 400, 400), ("0", 0, 50), ("0.03", 30, 50),
    (" 3 ", 3000, 3000), ("1.5", 1500, 1500), ("0.0005", 0, 50), ("0.0015", 2, 50),
    ("0.0025", 2, 50), ("-1", -1, -1), ("-0.001", -1, -1), ("", -1, -1),
    ("soon", -1, -1), ("True", -1, -1), ("1,5", -1, -1), ("1e3", 1000000, 1000000),
    ("1e9", 604800000, 604800000),
    ("604800", 604800000, 604800000), ("999999999", 604800000, 604800000),
    ("60", 60000, 60000),
]

# (due, period, now) -> when it runs next
# A little late, the next moment of the grid; a whole period late or more
# (the screen was away), a full period from now.
GRID = [
    ((1000, 1000, 1000), 2000), ((1000, 1000, 1004), 2000), ((1000, 1000, 1999), 2000),
    ((1000, 1000, 2000), 3000), ((1000, 1000, 2001), 3001), ((1000, 1000, 5300), 6300),
    ((1000, 1000, 900), 2000),
    ((50, 50, 50), 100), ((50, 50, 99), 100), ((50, 50, 1234), 1284),
    ((7300, 250, 99999), 100249), ((0, 604800000, 1), 604800000),
]


def _run(queue):
    """A Handler in ten lines: what woke it, in the order it would."""
    class Desk:
        def __init__(self):
            self.at = 0
            self.queue = []
            self.count = 0

        def now(self):
            return self.at

        def wake(self, millis, work):
            self.count += 1
            self.queue.append((self.at + millis, self.count, work))
            return self.count

        def unwake(self, handle):
            self.queue = [item for item in self.queue if item[1] != handle]

        def until(self, moment):
            while True:
                due = sorted(item for item in self.queue if item[0] <= moment)
                if not due:
                    break
                self.queue.remove(due[0])
                self.at = max(self.at, due[0][0])
                due[0][2]()
            self.at = moment
    return Desk()


class TheRules(unittest.TestCase):
    """What a time is, and where the moments of an every() fall."""

    def test_seconds_are_read_as_whole_milliseconds(self):
        for written, once, again in TIMES:
            self.assertEqual(rules.timer_millis(written, False), once, repr(written))
            self.assertEqual(rules.timer_millis(written, True), again, repr(written))

    def test_a_number_is_read_as_its_text(self):
        self.assertEqual(rules.timer_millis(2, False), 2000)
        self.assertEqual(rules.timer_millis(0.4, True), 400)
        self.assertEqual(rules.timer_millis(True, False), -1)
        self.assertEqual(rules.timer_millis(None, False), -1)

    def test_the_moments_are_a_grid_that_a_late_run_does_not_move(self):
        for given, wanted in GRID:
            self.assertEqual(rules.timer_next(*given), wanted, given)

    @needs_sdk
    def test_the_two_languages_agree(self):
        lines = []
        for index, (written, _once, _again) in enumerate(TIMES):
            lines.append('System.out.println("t%d|" + ApkpyKitRules.timerMillis("%s", false) '
                         '+ "|" + ApkpyKitRules.timerMillis("%s", true));'
                         % (index, written, written))
        for index, (given, _wanted) in enumerate(GRID):
            lines.append('System.out.println("g%d|" + ApkpyKitRules.timerNext(%dL, %dL, %dL));'
                         % ((index,) + given))
        if not TOOLING:
            self.skipTest("no JDK on this machine")
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-timer-rules-")
        with io.open(os.path.join(work, "ApkpyKitRules.java"), "w", encoding="utf-8") as handle:
            handle.write(kit.java_source("ApkpyKitRules", "p").replace("package p;", ""))
        with io.open(os.path.join(work, "Harness.java"), "w", encoding="utf-8") as handle:
            handle.write("public class Harness {\n    public static void main(String[] a) {\n"
                         "        " + "\n        ".join(lines) + "\n    }\n}\n")
        built = subprocess.run([javac, "-encoding", "UTF-8", "-d", work,
                                os.path.join(work, "ApkpyKitRules.java"),
                                os.path.join(work, "Harness.java")],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java_bin, "-cp", work, "Harness"], capture_output=True, text=True)
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)
        answers = dict(line.split("|", 1) for line in ran.stdout.splitlines())
        self.assertEqual(len(answers), len(TIMES) + len(GRID))
        for index, (written, once, again) in enumerate(TIMES):
            self.assertEqual(answers["t%d" % index], "%d|%d" % (once, again), repr(written))
        for index, (given, wanted) in enumerate(GRID):
            self.assertEqual(answers["g%d" % index], str(wanted), given)
        shutil.rmtree(work, ignore_errors=True)

    def test_the_limits_are_written_into_the_java(self):
        source = kit.java_source("ApkpyKitRules", "p")
        self.assertIn("%dL" % rules.TIMER_SHORTEST, source)
        self.assertIn("%dL" % rules.TIMER_LONGEST, source)


class WhatIsBuilt(unittest.TestCase):

    BODY = ('timer.every(1, tick)\n'
            'timer.after(2.5, hide)\n'
            'word = timer.cancel(tick)\n'
            'if timer.running(hide):\n'
            '    out.set_value(word)')

    def test_each_call_is_one_line_and_a_function_crosses_as_its_name(self):
        java = _java(self.BODY, TICK)
        self.assertIn('_apkpyNative_timer_every(String.valueOf(1), String.valueOf("tick"));', java)
        self.assertIn('_apkpyNative_timer_after(String.valueOf(2.5), String.valueOf("hide"));', java)
        self.assertIn("return ApkpyTimers.every(this, seconds, run);", java)
        self.assertIn("return ApkpyTimers.after(this, seconds, run);", java)
        self.assertIn("return ApkpyTimers.cancel(this, run);", java)
        self.assertIn("return ApkpyTimers.running(this, run);", java)

    def test_a_yes_or_no_is_asked_of_the_word(self):
        java = _java(self.BODY, TICK)
        self.assertIn('_apkpyNative_timer_running(String.valueOf("hide")))).equals("True")', java)

    def test_every_screen_says_how_its_timed_functions_are_called(self):
        top = TICK + ('def never():\n    out.set_value("no timer calls this")\n\n'
                      'other = Screen(id="other")\n'
                      'label("Second", id="second", screen=other)\n\n')
        files = _built(self.BODY, top)
        for name in ("java/Screen_homeActivity.java", "java/Screen_otherActivity.java"):
            java = files[name]
            self.assertIn("ApkpyTimers.host(this,", java, name)
            self.assertIn('if ("hide".equals(name)) pythonCallback_hide();', java, name)
            self.assertIn('else if ("tick".equals(name)) pythonCallback_tick();', java, name)
            self.assertNotIn('"never".equals(name)', java, name)
            self.assertNotIn('"go".equals(name)', java, name)
            # The function a name leads to is in the same class.
            self.assertIn("private void pythonCallback_tick()", java, name)
            self.assertEqual(java.count("ApkpyTimers.host("), 1, name)

    def test_only_what_it_needs_goes_into_the_app(self):
        files = _built('timer.every(1, tick)', TICK)
        self.assertEqual(sorted(name for name in files if name.startswith("java/Apkpy")),
                         ["java/ApkpyKit.java", "java/ApkpyKitRules.java",
                          "java/ApkpyTimers.java", "java/ApkpyValues.java", "java/ApkpyWeight.java"])
        manifest = files["AndroidManifest.xml"]
        self.assertNotIn("uses-permission", manifest)
        self.assertNotIn("ApkpyKitActivity", manifest)

    def test_an_app_with_no_timer_has_none_of_it(self):
        files = _built('out.set_value("x")', TICK)
        self.assertNotIn("java/ApkpyTimers.java", files)
        self.assertNotIn("Timer", files["java/Screen_homeActivity.java"])
        other = _built('haptics.tap()', TICK)
        self.assertNotIn("ApkpyTimers", other["java/Screen_homeActivity.java"])

    def test_the_seconds_can_be_worked_out_while_the_app_runs(self):
        top = TICK + 'wait = inputs("Seconds", id="wait", screen=home)\n\n'
        java = _java('timer.after(wait.get_value(), hide)', top)
        self.assertRegex(java, r'_apkpyNative_timer_after\(String\.valueOf\(.*getText\(\)'
                               r'.*String\.valueOf\("hide"\)\);')

    def test_a_function_can_stop_its_own_timer(self):
        top = ('def tick():\n'
               '    timer.cancel(tick)\n'
               '    timer.after(1, tick)\n\n')
        java = _java('timer.every(1, tick)', top)
        self.assertIn('_apkpyNative_timer_cancel(String.valueOf("tick"));', java)

    def test_a_name_the_app_made_its_own_is_left_alone(self):
        top = ('timer = label("00:00", id="timer", screen=home)\n\n')
        java = _java('timer.set_value("00:01")', top)
        self.assertNotIn("ApkpyTimers", java)


class WhatStopsTheBuild(unittest.TestCase):

    def _stops(self, body, *words, top=TICK, code="U2048"):
        text = _error(body, top)
        self.assertIn(code, text)
        for word in words:
            self.assertIn(word, text)
        return text

    def test_what_is_called_has_to_be_a_function_of_the_app(self):
        for body in ('timer.every(1, lambda: out.set_value("x"))',
                     'timer.after(2, out.hide)',
                     'timer.after(2, "tick")',
                     'timer.cancel(toast)',
                     'timer.running(nowhere)'):
            self._stops(body, "run= has to be a function you defined")

    def test_the_brackets_run_the_function_on_the_spot(self):
        self._stops('timer.every(1, tick())',
                    "tick() is called here, and the timer is handed what it answers",
                    "timer.every(1, tick)")

    def test_the_seconds_come_first(self):
        self._stops('timer.every(tick, 1)',
                    "timer.every() takes the seconds first, then the function",
                    "timer.every(1, tick)")

    def test_a_timer_has_nothing_to_hand_over(self):
        top = 'def count(value):\n    out.set_value(value)\n\n'
        text = self._stops('timer.every(1, count)', top=top)
        self.assertIn("count() is called by a timer with nothing, and it takes value", text)
        self.assertIn("def count():", text)

    def test_a_function_inside_another_has_no_name_to_call(self):
        self._stops('def inner():\n    out.set_value("x")\ntimer.after(1, inner)',
                    "run= has to be a function you defined")

    def test_a_time_written_wrong(self):
        self._stops('timer.after("soon", hide)', "seconds= is a number")
        self._stops('timer.after(-1, hide)', "seconds= is zero or more, got -1")
        self._stops('timer.after(2)', "timer.after() needs run")
        self._stops('timer.after(hide)', "timer.after() takes the seconds first")
        self._stops('timer.every()', "timer.every() needs seconds")
        self._stops('timer.every(1, tick, 3)', "at most 2 arguments")
        self._stops('timer.every(1, tick, on_result=answered)', "timer.every() has no on_result=")

    def test_a_call_that_does_not_exist(self):
        self._stops('timer.stop(tick)', "timer has no stop()", "timer.cancel(run)")
        self._stops('out.set_value(timer.running)', "is missing its brackets")

    def test_a_timer_is_started_by_a_function_not_by_the_top_of_the_file(self):
        source = HEAD + TICK + 'timer.every(1, tick)\n\ndef go():\n    out.set_value("x")\n' + TAIL
        text = " ".join(translate_python_to_android(source)["error.txt"].split())
        self.assertIn("U2048", text)
        self.assertIn("timer.every() at the top of the file starts before there is a screen", text)
        self.assertIn("lifecycle(home, on_mount=start)", text)

    def test_started_when_the_screen_opens(self):
        source = (HEAD + TICK + 'def start():\n    timer.every(1, tick)\n\n'
                  'lifecycle(home, on_mount=start)\n\ndef go():\n    timer.cancel(tick)\n' + TAIL)
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files)
        self.assertIn("pythonCallback_start();", files["java/Screen_homeActivity.java"])

    def test_sleep_is_told_about_the_timer(self):
        # The advice was in the table and was never said: time is in none of
        # the lists of modules that table was read through.
        source = HEAD + 'def go():\n    time.sleep(2)\n    out.set_value("done")\n' + TAIL
        text = " ".join(translate_python_to_android(source)["error.txt"].split())
        self.assertIn("U2033", text)
        self.assertIn("Write it as timer.after(seconds, function)", text)

    def test_every_line_to_write_instead_is_said(self):
        from apkpy_lib.core import unsupported
        for name, line in unsupported.REPLACEMENTS.items():
            _cause, tips = unsupported.advice(name)
            self.assertIn("Write it as " + line + ".", tips, name)

    def test_inside_a_background_job(self):
        source = (HEAD + TICK +
                  'def work(job):\n'
                  '    timer.after(1, hide)\n\n'
                  'sync = background_job("sync", run=work)\n'
                  'def go():\n'
                  '    sync.enqueue()\n' + TAIL)
        text = " ".join(translate_python_to_android(source).get("error.txt", "").split())
        self.assertIn("J7004", text)
        self.assertIn("timer.after() cannot run inside a background job", text)


class TheClockwork(unittest.TestCase):
    """The Previewer's timers with a clock of the test's own: ApkpyTimers is
    the same steps, and the phone is where those are seen."""

    def setUp(self):
        self.desk = _run([])
        self.clock = preview._Clockwork(self.desk.now, self.desk.wake, self.desk.unwake)
        self.seen = []
        self.clock.shown("home")

    def _note(self, word):
        return lambda: self.seen.append((word, self.desk.at))

    def test_after_runs_once(self):
        self.assertEqual(self.clock.start("home", "2", "hide", self._note("hide"), False), "ok")
        self.assertTrue(self.clock.running("home", "hide"))
        self.desk.until(1999)
        self.assertEqual(self.seen, [])
        self.desk.until(10000)
        self.assertEqual(self.seen, [("hide", 2000)])
        self.assertFalse(self.clock.running("home", "hide"))

    def test_every_keeps_to_its_grid(self):
        self.clock.start("home", 1, "tick", self._note("tick"), True)
        self.desk.until(3500)
        self.assertEqual(self.seen, [("tick", 1000), ("tick", 2000), ("tick", 3000)])
        self.assertTrue(self.clock.running("home", "tick"))

    def test_a_run_that_came_late_does_not_push_the_next_one_late(self):
        self.clock.start("home", 1, "tick", self._note("tick"), True)
        # The thread was busy: what was due at 1000 runs at 1300.
        late = self.desk.queue[0]
        self.desk.queue = [(1300, late[1], late[2])]
        self.desk.until(2100)
        self.assertEqual(self.seen, [("tick", 1300), ("tick", 2000)])

    def test_a_time_that_is_not_one_starts_nothing(self):
        for wrong in ("", "soon", -1, None, True):
            self.assertEqual(self.clock.start("home", wrong, "tick", self._note("tick"), True),
                             "invalid")
        self.assertFalse(self.clock.running("home", "tick"))
        self.assertEqual(self.desk.queue, [])

    def test_starting_again_starts_over(self):
        # Typing: every key puts the search off again.
        for moment in (0, 100, 200, 300):
            self.desk.until(moment)
            self.clock.start("home", 0.4, "search", self._note("search"), False)
        self.desk.until(5000)
        self.assertEqual(self.seen, [("search", 700)])

    def test_cancel_names_the_function(self):
        self.clock.start("home", 1, "tick", self._note("tick"), True)
        self.clock.start("home", 1, "other", self._note("other"), True)
        self.desk.until(1500)
        self.assertEqual(self.clock.cancel("home", "tick"), "ok")
        self.assertEqual(self.clock.cancel("home", "tick"), "not_running")
        self.assertEqual(self.clock.cancel("home", "never"), "not_running")
        self.desk.until(2500)
        self.assertEqual([word for word, _at in self.seen], ["tick", "other", "other"])

    def test_a_function_can_stop_itself_or_start_itself_over(self):
        def tick():
            self.seen.append(self.desk.at)
            if len(self.seen) == 3:
                self.clock.cancel("home", "tick")

        self.clock.start("home", 1, "tick", tick, True)
        self.desk.until(9000)
        self.assertEqual(self.seen, [1000, 2000, 3000])

        self.seen = []
        inside = []

        def again():
            inside.append(self.clock.running("home", "again"))
            self.seen.append(self.desk.at)
            if len(self.seen) < 3:
                self.clock.start("home", 0.5, "again", again, False)

        self.clock.start("home", 0.5, "again", again, False)
        self.desk.until(20000)
        self.assertEqual(self.seen, [9500, 10000, 10500])
        # Inside an after() its timer is over already.
        self.assertEqual(inside, [False, False, False])

    def test_a_screen_that_is_not_on_show_runs_nothing_and_misses_nothing(self):
        self.clock.start("home", 1, "tick", self._note("tick"), True)
        self.clock.start("home", 5, "hide", self._note("hide"), False)
        self.desk.until(2200)
        self.clock.shown("detail")
        self.desk.until(7300)
        self.assertEqual(self.seen, [("tick", 1000), ("tick", 2000)])
        self.assertTrue(self.clock.running("home", "tick"))
        self.clock.shown("home")
        self.desk.until(7300)
        # What fell due runs once each, at once -- not five ticks in a burst.
        self.assertEqual(sorted(self.seen[2:]), [("hide", 7300), ("tick", 7300)])
        # And it goes on from there: the next is a full second on, not at
        # 8000, where the old grid would have put it right behind this one.
        self.desk.until(10400)
        self.assertEqual(self.seen[4:], [("tick", 8300), ("tick", 9300), ("tick", 10300)])

    def test_away_for_less_than_a_period_the_grid_is_kept(self):
        self.clock.start("home", 1, "tick", self._note("tick"), True)
        self.desk.until(1700)
        self.clock.shown("detail")
        self.desk.until(2400)           # the moment at 2000 went by, 400 ms ago
        self.clock.shown("home")
        self.desk.until(4100)
        self.assertEqual(self.seen, [("tick", 1000), ("tick", 2400), ("tick", 3000), ("tick", 4000)])

    def test_what_is_not_due_yet_keeps_its_moment(self):
        self.clock.start("home", 10, "hide", self._note("hide"), False)
        self.desk.until(2000)
        self.clock.shown("detail")
        self.desk.until(4000)
        self.clock.shown("home")
        self.desk.until(60000)
        self.assertEqual(self.seen, [("hide", 10000)])

    def test_each_screen_has_its_own(self):
        self.clock.start("home", 1, "tick", self._note("home"), True)
        self.clock.shown("detail")
        self.clock.start("detail", 1, "tick", self._note("detail"), True)
        self.assertEqual(self.clock.cancel("detail", "tick"), "ok")
        self.assertTrue(self.clock.running("home", "tick"))
        self.assertFalse(self.clock.running("detail", "tick"))

    def test_started_before_any_screen_it_goes_to_the_first(self):
        clock = preview._Clockwork(self.desk.now, self.desk.wake, self.desk.unwake)
        clock.start(None, 1, "tick", self._note("tick"), True)
        clock.shown("home")
        self.assertTrue(clock.running("home", "tick"))
        self.desk.until(1100)
        self.assertEqual(self.seen, [("tick", 1000)])


def _plain():
    pass


def _takes(value):
    pass


class OnTheDesk(unittest.TestCase):
    """With no window nothing is on show, so nothing runs; what is refused is
    refused as the build refuses it."""

    def tearDown(self):
        apkpy_lib.timer._clockwork.forget()

    def _said(self, call):
        with self.assertRaises(ApkpyError) as raised:
            call()
        self.assertEqual(raised.exception.code, "U2048")
        return str(raised.exception)

    def test_a_timer_waits_for_a_screen(self):
        self.assertEqual(apkpy_lib.timer.every(1, _plain), "ok")
        self.assertIs(apkpy_lib.timer.running(_plain), True)
        self.assertEqual(apkpy_lib.timer.after("x", _plain), "invalid")
        self.assertEqual(apkpy_lib.timer.cancel(_plain), "ok")
        self.assertEqual(apkpy_lib.timer.cancel(_plain), "not_running")
        self.assertIs(apkpy_lib.timer.running(_plain), False)

    def test_the_words_are_the_builds(self):
        cases = [
            (lambda: apkpy_lib.timer.every(1, lambda: None),
             'timer.every(1, lambda: out.set_value("x"))', TICK,
             "timer.every(): run= has to be a function you defined"),
            (lambda: apkpy_lib.timer.every(_plain, 1),
             'timer.every(tick, 1)', TICK,
             "timer.every() takes the seconds first, then the function"),
            (lambda: apkpy_lib.timer.after(1, _takes),
             'timer.after(1, count)', 'def count(value):\n    out.set_value(value)\n\n',
             "is called by a timer with nothing, and it takes value"),
            (lambda: apkpy_lib.timer.cancel("tick"),
             'timer.cancel("tick")', TICK,
             "timer.cancel(): run= has to be a function you defined"),
        ]
        for call, body, top, words in cases:
            self.assertIn(words, self._said(call))
            self.assertIn(words, _error(body, top))

    def test_the_top_of_the_file_is_refused_as_the_build_refuses_it(self):
        # No window is opened for this: a fixture left half made would be
        # in the way of every test after it.
        body = ('from apkpy_lib import timer\n'
                'def tick():\n'
                '    pass\n'
                'timer.every(1, tick)\n')
        with self.assertRaises(ApkpyError) as raised:
            exec(body, {})
        self.assertEqual(raised.exception.code, "U2048")
        self.assertIn("timer.every() at the top of the file starts before there is a screen",
                      str(raised.exception))
        self.assertIs(apkpy_lib.timer._clockwork.running(None, "tick"), False)

    def test_a_job_body_is_refused_with_the_builds_words(self):
        with job_rules.running_job():
            for call in (lambda: apkpy_lib.timer.after(1, _plain),
                         lambda: apkpy_lib.timer.every(1, _plain),
                         lambda: apkpy_lib.timer.cancel(_plain),
                         lambda: apkpy_lib.timer.running(_plain)):
                with self.assertRaises(ApkpyError) as raised:
                    call()
                self.assertEqual(raised.exception.code, "J7004")
                self.assertIn("cannot run inside a background job", str(raised.exception))


class InThePreviewer(unittest.TestCase):
    """The window open, and real time going by."""

    APP = ('home = Screen(id="home")\n'
           'detail = Screen(id="detail")\n'
           'out = label("", id="out", screen=home)\n'
           'label("Detail", id="title", screen=detail)\n'
           'SEEN = []\n'
           'def tick():\n'
           '    SEEN.append("tick")\n'
           '    out.set_value(str(len(SEEN)))\n'
           'def late():\n'
           '    SEEN.append("late")\n'
           'def start():\n'
           '    return timer.every(0.05, tick), timer.after(0.15, late)\n')

    def tearDown(self):
        apkpy_lib.timer._clockwork.forget()

    def test_it_runs_with_the_window_and_waits_for_its_screen(self):
        with Previewed(self.APP, "") as shown:
            self.assertEqual(shown.ns["start"](), ("ok", "ok"))
            shown.settle(0.5)
            seen = list(shown.ns["SEEN"])
            self.assertGreaterEqual(seen.count("tick"), 4)
            self.assertEqual(seen.count("late"), 1)
            self.assertEqual(shown.widget("out").cget("text"), str(len(seen)))

            # Another screen comes to the front: nothing more is run.
            shown.app.render_screen(shown.ns["detail"])
            shown.settle(0.1)
            held = len(shown.ns["SEEN"])
            shown.settle(0.4)
            self.assertEqual(len(shown.ns["SEEN"]), held)
            self.assertIs(shown.ns["timer"].running(shown.ns["tick"]), False)

            # Back: it carries on.
            shown.app.go_back()
            shown.settle(0.3)
            self.assertGreater(len(shown.ns["SEEN"]), held)
            self.assertIs(shown.ns["timer"].running(shown.ns["tick"]), True)
            self.assertEqual(shown.ns["timer"].cancel(shown.ns["tick"]), "ok")
            ended = len(shown.ns["SEEN"])
            shown.settle(0.3)
            self.assertEqual(len(shown.ns["SEEN"]), ended)



if __name__ == "__main__":
    unittest.main()
