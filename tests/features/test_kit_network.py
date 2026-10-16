# -*- coding: utf-8 -*-
"""Whether the phone reaches the internet, over what, and being told when
that changes.

    if network.online(): ...        network.kind()        network.metered()
    network.on_change(changed)

Four calls of the same table as the rest of the kit. What these tests hold:
the phone and the desk make the three answers out of the same facts in the
same way, a function crosses to the phone as its name and every screen can be
asked for it, what cannot be built is refused in the same words on both
sides, a screen is told of a change once and only while it is on show -- and
on the desk the connection is the Previewer's to take away, so what an app
does without one can be seen there.
"""

import io
import os
import shutil
import subprocess
import tempfile
import threading
import unittest

import apkpy_lib
from apkpy_lib import job_rules, ui
from apkpy_lib import kit_rules as rules
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import kit
from apkpy_lib.diagnostics import ApkpyError
from apkpy_lib.features import jobs
from apkpy_lib.features import kit as preview

from test_data_rules import TOOLING
from test_kit import HEAD, TAIL, _built, _error, _java
from test_real_screens import Previewed

CHANGED = ('def changed():\n'
           '    out.set_value(network.kind())\n'
           '\n'
           'def queue():\n'
           '    out.set_value("queue")\n'
           '\n')

# (connected, wifi, mobile, ethernet) -> network.kind()
KINDS = [
    ((False, False, False, False), "none"), ((False, True, True, True), "none"),
    ((True, True, False, False), "wifi"), ((True, True, True, False), "wifi"),
    ((True, False, True, False), "mobile"), ((True, False, True, True), "mobile"),
    ((True, False, False, True), "ethernet"), ((True, False, False, False), "other"),
]
# (connected, internet, validated) -> network.online()
ONLINE = [
    ((True, True, True), True), ((True, True, False), False), ((True, False, True), False),
    ((False, True, True), False), ((False, False, False), False),
]
# (connected, unmetered) -> network.metered()
METERED = [((True, False), True), ((True, True), False), ((False, False), False),
           ((False, True), False)]
# (online, kind, metered) -> what a screen hears
STATES = [((True, "wifi", False), "online wifi"), ((True, "mobile", True), "online mobile metered"),
          ((False, "wifi", False), "offline wifi"), ((False, "none", False), "offline none"),
          ((True, "other", True), "online other metered")]


def _plain():
    pass


def _other():
    pass


def _takes(value):
    pass


_TOLD = []


def _told():
    _TOLD.append((apkpy_lib.network.online(), apkpy_lib.network.kind()))


def _java_bool(value):
    return "true" if value else "false"


class TheRules(unittest.TestCase):
    """What the three answers are made of."""

    def test_the_kind_is_the_first_that_is_true(self):
        for given, wanted in KINDS:
            self.assertEqual(rules.network_kind(*given), wanted, given)
            self.assertIn(wanted, rules.NETWORK_KINDS)

    def test_online_is_a_connection_seen_to_reach_the_internet(self):
        for given, wanted in ONLINE:
            self.assertIs(rules.network_online(*given), wanted, given)

    def test_nothing_is_paid_for_a_connection_that_is_not_there(self):
        for given, wanted in METERED:
            self.assertIs(rules.network_metered(*given), wanted, given)

    def test_what_a_screen_hears_is_the_three_as_one_text(self):
        for given, wanted in STATES:
            self.assertEqual(rules.network_state(*given), wanted)

    @unittest.skipUnless(TOOLING[0], "no JDK on this machine")
    def test_the_two_languages_agree(self):
        lines = []
        for index, (given, _wanted) in enumerate(KINDS):
            lines.append('System.out.println("k%d|" + ApkpyKitRules.networkKind(%s));'
                         % (index, ", ".join(_java_bool(each) for each in given)))
        for index, (given, _wanted) in enumerate(ONLINE):
            lines.append('System.out.println("o%d|" + ApkpyKitRules.networkOnline(%s));'
                         % (index, ", ".join(_java_bool(each) for each in given)))
        for index, (given, _wanted) in enumerate(METERED):
            lines.append('System.out.println("m%d|" + ApkpyKitRules.networkMetered(%s));'
                         % (index, ", ".join(_java_bool(each) for each in given)))
        for index, ((online, kind, metered), _wanted) in enumerate(STATES):
            lines.append('System.out.println("s%d|" + ApkpyKitRules.networkState(%s, "%s", %s));'
                         % (index, _java_bool(online), kind, _java_bool(metered)))
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-network-rules-")
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
        self.assertEqual(len(answers), len(KINDS) + len(ONLINE) + len(METERED) + len(STATES))
        for index, (_given, wanted) in enumerate(KINDS):
            self.assertEqual(answers["k%d" % index], wanted)
        for index, (_given, wanted) in enumerate(ONLINE):
            self.assertEqual(answers["o%d" % index], _java_bool(wanted))
        for index, (_given, wanted) in enumerate(METERED):
            self.assertEqual(answers["m%d" % index], _java_bool(wanted))
        for index, (_given, wanted) in enumerate(STATES):
            self.assertEqual(answers["s%d" % index], wanted)


class WhatIsBuilt(unittest.TestCase):

    BODY = ('if network.online():\n'
            '    out.set_value(network.kind())\n'
            'if not network.metered():\n'
            '    out.set_value("free")\n'
            'word = network.on_change(changed)\n'
            'out.set_value(word)')

    def test_each_call_is_one_line_and_a_function_crosses_as_its_name(self):
        java = _java(self.BODY, CHANGED)
        self.assertIn("return ApkpyNetwork.online(this);", java)
        self.assertIn("return ApkpyNetwork.kind(this);", java)
        self.assertIn("return ApkpyNetwork.metered(this);", java)
        self.assertIn("return ApkpyNetwork.onChange(this, run);", java)
        self.assertIn('_apkpyNative_network_on_change(String.valueOf("changed"))', java)

    def test_a_yes_or_no_is_asked_of_the_word(self):
        java = _java(self.BODY, CHANGED)
        self.assertIn('_apkpyNative_network_online())).equals("True")', java)
        self.assertIn('_apkpyNative_network_metered())).equals("True")', java)

    def test_every_screen_says_how_its_watched_functions_are_called(self):
        top = CHANGED + ('other = Screen(id="other")\n'
                         'label("Second", id="second", screen=other)\n\n')
        files = _built('network.on_change(changed)\nnetwork.on_change(queue)', top)
        for name in ("java/Screen_homeActivity.java", "java/Screen_otherActivity.java"):
            java = files[name]
            self.assertEqual(java.count("ApkpyNetwork.host(this,"), 1, name)
            self.assertIn('if ("changed".equals(name)) pythonCallback_changed();', java, name)
            self.assertIn('else if ("queue".equals(name)) pythonCallback_queue();', java, name)
            self.assertNotIn('"go".equals(name)', java, name)
            self.assertIn("private void pythonCallback_changed()", java, name)
            self.assertNotIn("ApkpyTimers", java, name)

    def test_an_app_that_only_asks_has_nothing_called_by_name(self):
        files = _built('if network.online():\n    out.set_value("on")', CHANGED)
        java = files["java/Screen_homeActivity.java"]
        self.assertIn("return ApkpyNetwork.online(this);", java)
        self.assertNotIn("ApkpyNetwork.host(", java)
        self.assertNotIn("ApkpyNetwork.Calls", java)

    def test_only_what_it_needs_goes_into_the_app(self):
        files = _built('network.on_change(changed)', CHANGED)
        self.assertEqual(sorted(name for name in files if name.startswith("java/Apkpy")),
                         ["java/ApkpyKit.java", "java/ApkpyKitRules.java",
                          "java/ApkpyNetwork.java", "java/ApkpyWeight.java"])
        manifest = files["AndroidManifest.xml"]
        # The one permission, a normal one: nobody is asked for it.
        self.assertEqual([line.strip() for line in manifest.splitlines() if "uses-permission" in line],
                         ['<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />'])
        self.assertNotIn("ApkpyKitActivity", manifest)

    def test_an_app_with_none_of_it_has_none_of_it(self):
        files = _built('out.set_value("x")')
        self.assertNotIn("java/ApkpyNetwork.java", files)
        self.assertNotIn("Network", files["java/Screen_homeActivity.java"])
        self.assertNotIn("ACCESS_NETWORK_STATE", files["AndroidManifest.xml"])

    def test_timers_and_the_connection_are_each_called_by_their_own(self):
        top = CHANGED + 'def tick():\n    out.set_value("tick")\n\n'
        java = _java('timer.every(30, tick)\nnetwork.on_change(changed)', top)
        self.assertEqual(java.count("ApkpyTimers.host(this,"), 1)
        self.assertEqual(java.count("ApkpyNetwork.host(this,"), 1)
        timers, network = java.split("ApkpyTimers.host(this,")[1].split("ApkpyNetwork.host(this,")
        self.assertIn('"tick".equals(name)', timers)
        self.assertNotIn('"changed".equals(name)', timers)
        self.assertIn('"changed".equals(name)', network)
        self.assertNotIn('"tick".equals(name)', network)

    def test_a_name_the_app_made_its_own_is_left_alone(self):
        source = (HEAD + 'network = inputs("Network", id="network", screen=home)\n'
                  'def go():\n    out.set_value(network.get_value())\n' + TAIL)
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files)
        self.assertNotIn("java/ApkpyNetwork.java", files)

    def test_the_class_is_written_for_the_app(self):
        source = kit.java_source("ApkpyNetwork", "com.example.app")
        self.assertTrue(source.startswith("package com.example.app;"))
        self.assertNotIn("__", source.replace("__PACKAGE__", ""))
        # What it reads is what Android gives every app; nothing is asked of
        # the person, and nothing is looked up that needs another permission.
        for forbidden in ("WifiManager", "TelephonyManager", "getSSID", "LOCATION"):
            self.assertNotIn(forbidden, source)


class WhatStopsTheBuild(unittest.TestCase):

    def _stops(self, body, *words, top=CHANGED, code="U2048"):
        text = _error(body, top)
        self.assertIn(code, text)
        for word in words:
            self.assertIn(word, text)
        return text

    def test_what_is_told_has_to_be_a_function_of_the_app(self):
        for body in ('network.on_change(lambda: out.set_value("x"))',
                     'network.on_change(out.hide)',
                     'network.on_change("changed")',
                     'network.on_change(toast)'):
            text = self._stops(body, "network.on_change(): run= has to be a function you defined",
                               "network.on_change(changed)")
            self.assertIn("when the connection changes", text)
            self.assertNotIn("timer", text)

    def test_the_brackets_run_the_function_on_the_spot(self):
        text = self._stops('network.on_change(queue())',
                           "queue() is called here, and network.on_change() is handed what it answers",
                           "Write the name alone: network.on_change(queue)")
        self.assertNotIn("timer", text)

    def test_it_is_told_that_something_changed_and_asks_what(self):
        top = 'def show(online):\n    out.set_value(online)\n\n'
        text = self._stops('network.on_change(show)', top=top)
        self.assertIn("show() is called with nothing when the connection changes, "
                      "and it takes online", text)
        self.assertIn("network.online() and network.kind()", text)
        self.assertIn("def show():", text)

    def test_what_is_written_wrong(self):
        self._stops('network.on_change()', "network.on_change() needs run")
        self._stops('network.on_change(changed, queue)', "at most 1 argument")
        self._stops('network.online(on_result=answered)', "network.online() has no on_result=",
                    "answers at once")
        self._stops('network.kind("wifi")', "network.kind() takes no arguments")
        self._stops('out.set_value(network.kind)', "network.kind() is missing its brackets")
        self._stops('if network.online:\n    out.set_value("on")',
                    "network.online() is missing its brackets")

    def test_a_call_that_does_not_exist(self):
        self._stops('network.is_online()', "network has no is_online()", "network.online()")
        self._stops('network.type()', "network has no type()", "kind()")
        self._stops('network.off_change(changed)', "network has no off_change()",
                    "network.on_change(run)")

    def test_it_is_asked_for_by_a_function_not_by_the_top_of_the_file(self):
        source = HEAD + CHANGED + 'network.on_change(changed)\n\ndef go():\n    out.set_value("x")\n' + TAIL
        text = " ".join(translate_python_to_android(source)["error.txt"].split())
        self.assertIn("U2048", text)
        self.assertIn("network.on_change() at the top of the file starts before there is a screen",
                      text)
        self.assertIn("What is watched belongs to the screen", text)
        self.assertIn("lifecycle(home, on_mount=start)", text)

    def test_asked_for_when_the_screen_opens(self):
        source = (HEAD + CHANGED + 'def start():\n    changed()\n    network.on_change(changed)\n\n'
                  'lifecycle(home, on_mount=start)\n\ndef go():\n    out.set_value("x")\n' + TAIL)
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files)
        self.assertIn("pythonCallback_start();", files["java/Screen_homeActivity.java"])

    def test_inside_a_background_job(self):
        source = (HEAD + CHANGED +
                  'def work(job):\n'
                  '    kind = network.kind()\n\n'
                  'sync = background_job("sync", run=work)\n'
                  'def go():\n'
                  '    sync.enqueue()\n' + TAIL)
        text = " ".join(translate_python_to_android(source).get("error.txt", "").split())
        self.assertIn("J7004", text)
        self.assertIn("network.kind() cannot run inside a background job", text)


class TheWatchers(unittest.TestCase):
    """Who is told what, with a connection of the test's own. ApkpyNetwork is
    the same steps, and test_kit_network_java runs those."""

    def setUp(self):
        self.now = "online wifi"
        self.watch = preview._Watchers(lambda: self.now)
        self.seen = []
        self.watch.shown("home")

    def _add(self, screen, name):
        return self.watch.add(screen, name, lambda: self.seen.append((screen, name, self.now)))

    def _becomes(self, state):
        self.now = state
        self.watch.changed()

    def test_it_is_told_of_a_change_and_not_of_how_things_are(self):
        self.assertEqual(self._add("home", "changed"), "ok")
        self.watch.changed()
        self.assertEqual(self.seen, [])
        self._becomes("offline none")
        self._becomes("offline none")
        self._becomes("online mobile metered")
        self.assertEqual(self.seen, [("home", "changed", "offline none"),
                                     ("home", "changed", "online mobile metered")])

    def test_every_function_once_in_the_order_they_were_given(self):
        self._add("home", "banner")
        self._add("home", "queue")
        self._add("home", "banner")
        self._becomes("offline none")
        self.assertEqual([name for _screen, name, _state in self.seen], ["banner", "queue"])

    def test_a_screen_not_on_show_is_not_told(self):
        self._add("home", "changed")
        self.watch.shown("detail")
        self._becomes("offline none")
        self._becomes("online wifi")
        self.watch.shown("home")
        self.watch.changed()
        self.assertEqual(self.seen, [])         # it came and went

    def test_back_on_show_it_is_told_once_if_it_is_still_so(self):
        self._add("home", "changed")
        self.watch.shown("detail")
        self._becomes("offline none")
        self._becomes("offline wifi")
        self.assertEqual(self.seen, [])
        self.watch.shown("home")
        self.watch.changed()
        self.watch.changed()
        self.assertEqual(self.seen, [("home", "changed", "offline wifi")])

    def test_each_screen_remembers_what_it_heard(self):
        self._add("home", "changed")
        self.watch.shown("detail")
        self._add("detail", "changed")
        self._becomes("offline none")
        self.watch.shown("home")
        self.watch.changed()
        self.assertEqual([(screen, state) for screen, _name, state in self.seen],
                         [("detail", "offline none"), ("home", "offline none")])

    def test_asked_before_any_screen_it_goes_to_the_first(self):
        watch = preview._Watchers(lambda: self.now)
        watch.add(None, "changed", lambda: self.seen.append("told"))
        watch.shown("home")
        self.now = "offline none"
        watch.changed()
        self.assertEqual(self.seen, ["told"])

    def test_a_function_can_ask_for_another_while_it_is_told(self):
        def first():
            self.seen.append("first")
            self.watch.add("home", "second", lambda: self.seen.append("second"))
        self.watch.add("home", "first", first)
        self._becomes("offline none")
        self._becomes("online wifi")
        self.assertEqual(self.seen, ["first", "first", "second"])


class OnTheDesk(unittest.TestCase):
    """With no window: the desk's connection, and the build's own refusals."""

    def setUp(self):
        apkpy_lib.network._watchers.forget()
        apkpy_lib.network._kind = "wifi"

    tearDown = setUp

    def _said(self, call):
        with self.assertRaises(ApkpyError) as raised:
            call()
        self.assertEqual(raised.exception.code, "U2048")
        return str(raised.exception)

    def test_a_desk_is_on_wifi_until_the_previewer_says_otherwise(self):
        network = apkpy_lib.network
        self.assertIs(network.online(), True)
        self.assertEqual(network.kind(), "wifi")
        self.assertIs(network.metered(), False)
        self.assertEqual(network._switch(), "mobile")
        self.assertEqual((network.online(), network.kind(), network.metered()),
                         (True, "mobile", True))
        self.assertEqual(network._switch(), "none")
        self.assertEqual((network.online(), network.kind(), network.metered()),
                         (False, "none", False))
        self.assertIs(preview.offline(), True)
        self.assertEqual(network._switch(), "wifi")
        self.assertIs(preview.offline(), False)
        with self.assertRaises(ValueError):
            network._switch("satellite")

    def test_every_kind_the_desk_can_be_is_one_the_phone_can_answer(self):
        for kind in apkpy_lib.network._SWITCH:
            self.assertIn(kind, rules.NETWORK_KINDS)
            self.assertIn(kind, ui._STATUS_CONNECTION)

    def test_the_function_is_told_when_the_previewer_changes_the_connection(self):
        del _TOLD[:]
        self.assertEqual(apkpy_lib.network.on_change(_told), "ok")
        apkpy_lib.network._switch("none")
        apkpy_lib.network._switch("none")
        apkpy_lib.network._switch("wifi")
        self.assertEqual(_TOLD, [(False, "none"), (True, "wifi")])

    def test_with_no_connection_a_request_fails_as_it_does_on_the_phone(self):
        # No window: the answer comes back on the thread that asked. The host
        # is one that exists nowhere, so the words can only be ApkPy's own --
        # a request that had left would have come back with the machine's.
        got, done = [], threading.Event()

        def answered(ok, text):
            got.append((ok, text))
            done.set()

        kept, ui._app = ui._app, None
        try:
            apkpy_lib.network._switch("none")
            apkpy_lib.https.get("https://example.invalid/x", on_response=answered)
            self.assertTrue(done.wait(10))
        finally:
            ui._app = kept
        self.assertEqual(got, [(False, 'Unable to resolve host "example.invalid": '
                                       'No address associated with hostname')])

    def test_the_words_are_the_builds(self):
        cases = [
            (lambda: apkpy_lib.network.on_change(lambda: None),
             'network.on_change(lambda: out.set_value("x"))', CHANGED,
             "network.on_change(): run= has to be a function you defined"),
            (lambda: apkpy_lib.network.on_change(_takes),
             'network.on_change(show)', 'def show(value):\n    out.set_value(value)\n\n',
             "is called with nothing when the connection changes, and it takes value"),
            (lambda: apkpy_lib.network.on_change("changed"),
             'network.on_change("changed")', CHANGED,
             "network.on_change(): run= has to be a function you defined"),
            (lambda: apkpy_lib.network.is_online(),
             'network.is_online()', CHANGED, "network has no is_online()"),
        ]
        for call, body, top, words in cases:
            self.assertIn(words, self._said(call))
            self.assertIn(words, _error(body, top))

    def test_the_top_of_the_file_is_refused_as_the_build_refuses_it(self):
        body = ('from apkpy_lib import network\n'
                'def changed():\n'
                '    pass\n'
                'network.on_change(changed)\n')
        with self.assertRaises(ApkpyError) as raised:
            exec(body, {})
        self.assertEqual(raised.exception.code, "U2048")
        self.assertIn("network.on_change() at the top of the file starts before there is a screen",
                      str(raised.exception))
        self.assertEqual(apkpy_lib.network._watchers._watching, {})

    def test_a_job_body_is_refused_with_the_builds_words(self):
        with job_rules.running_job():
            for call in (apkpy_lib.network.online, apkpy_lib.network.kind,
                         apkpy_lib.network.metered,
                         lambda: apkpy_lib.network.on_change(_plain)):
                with self.assertRaises(ApkpyError) as raised:
                    call()
                self.assertEqual(raised.exception.code, "J7004")
                self.assertIn("cannot run inside a background job", str(raised.exception))

    def test_with_no_connection_the_queue_waits_whatever_the_machine_reaches(self):
        apkpy_lib.network._switch("none")
        jobs._network_cache.update(online=True, checked_at=None)
        self.assertIs(jobs._online(), False)
        # And nothing was asked of the real one to find that out.
        self.assertIsNone(jobs._network_cache["checked_at"])


class _Click:
    def __init__(self, x):
        self.x = x


class InThePreviewer(unittest.TestCase):
    """The window open: the strip is the connection, and a click changes it."""

    APP = ('home = Screen(id="home")\n'
           'detail = Screen(id="detail")\n'
           'out = label("", id="out", screen=home)\n'
           'label("Detail", id="title", screen=detail)\n'
           'SEEN = []\n'
           'def changed():\n'
           '    SEEN.append((network.online(), network.kind(), network.metered()))\n'
           '    out.set_value("Online" if network.online() else "No connection")\n'
           'def start():\n'
           '    return network.on_change(changed)\n')

    def setUp(self):
        apkpy_lib.network._watchers.forget()
        apkpy_lib.network._kind = "wifi"

    tearDown = setUp

    def _over(self, glyph):
        order = ui._lit_status_glyphs() + ui._status_glyph_order()
        return _Click(order.index(glyph) * ui._STATUS_GLYPH_SIZE + ui._STATUS_GLYPH_SIZE // 2)

    def test_the_strip_draws_the_connection_and_a_click_on_it_changes_it(self):
        with Previewed(self.APP, "") as shown:
            app = shown.app
            self.assertEqual(shown.ns["start"](), "ok")
            self.assertEqual(ui._status_glyph_order(), ("signal", "wifi", "battery"))

            # The battery is not the connection: the click is left for the shade.
            self.assertIsNone(app._status_connection_click(self._over("battery")))
            self.assertEqual(shown.ns["network"].kind(), "wifi")

            self.assertEqual(app._status_connection_click(self._over("wifi")), "break")
            shown.settle(0.15)
            self.assertEqual(ui._status_glyph_order(), ("signal", "battery"))
            self.assertEqual(app._status_hint.cget("text"), "Mobile data")

            self.assertEqual(app._status_connection_click(self._over("signal")), "break")
            shown.settle(0.15)
            self.assertEqual(ui._status_glyph_order(), ("airplane", "battery"))
            self.assertEqual(shown.widget("out").cget("text"), "No connection")
            self.assertEqual(int(app._status_icons.cget("width")), 2 * ui._STATUS_GLYPH_SIZE)

            self.assertEqual(app._status_connection_click(self._over("airplane")), "break")
            shown.settle(0.15)
            self.assertEqual(shown.widget("out").cget("text"), "Online")
            self.assertEqual(shown.ns["SEEN"], [(True, "mobile", True), (False, "none", False),
                                                (True, "wifi", False)])

    def test_the_hint_says_what_it_is_and_that_it_can_be_changed(self):
        with Previewed(self.APP, "") as shown:
            app = shown.app
            app._status_connection_hover(self._over("wifi"))
            self.assertEqual(app._status_icons.cget("cursor"), "hand2")
            shown.settle(0.7)
            self.assertEqual(app._status_hint.cget("text"), "Wi-Fi · click to change")
            app._status_connection_hover(self._over("battery"))
            self.assertEqual(app._status_icons.cget("cursor"), "")
            self.assertIsNone(app._status_hint)

    def test_another_screen_on_show_and_the_first_is_told_when_it_is_back(self):
        with Previewed(self.APP, "") as shown:
            shown.ns["start"]()
            shown.app.render_screen(shown.ns["detail"])
            shown.settle(0.1)
            shown.ns["network"]._switch("none")
            shown.settle(0.15)
            self.assertEqual(shown.ns["SEEN"], [])
            shown.app.go_back()
            shown.settle(0.3)
            self.assertEqual(shown.ns["SEEN"], [(False, "none", False)])


if __name__ == "__main__":
    unittest.main()
