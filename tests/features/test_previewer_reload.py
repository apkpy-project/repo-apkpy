"""The Previewer reloads when a .py file of the app is saved.

apkpy_lib/reload.py: ``python writehere.py`` watches the folder and runs the
app in a second Python; a save starts the new code, which takes over only
once its window is drawn, and a change that does not start leaves the old
window up with the error on it.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apkpy_lib import reload  # noqa: E402


class WhichScriptsReloadTests(unittest.TestCase):

    def test_run_under_the_main_test(self):
        self.assertTrue(reload.calls_run(
            'from apkpy_lib import *\nhome = Screen(id="home")\n'
            'if __name__ == "__main__":\n    run(start_screen=home)\n'))

    def test_run_at_the_top_of_the_file(self):
        self.assertTrue(reload.calls_run("run()\n"))

    def test_the_main_test_written_the_other_way_round(self):
        self.assertTrue(reload.calls_run("if '__main__' == __name__:\n    run()\n"))

    def test_run_inside_a_main_function(self):
        self.assertTrue(reload.calls_run(
            "def main():\n    run(start_screen=home)\n\n"
            "if __name__ == '__main__':\n    main()\n"))

    def test_apkpy_lib_run(self):
        self.assertTrue(reload.calls_run("import apkpy_lib\napkpy_lib.run()\n"))

    def test_a_harness_that_calls_ui_run_is_left_alone(self):
        # Scripts that drive the Previewer from outside call ui.run: they
        # must not start running themselves in a second Python.
        self.assertFalse(reload.calls_run("from apkpy_lib import ui\nui.run()\n"))

    def test_a_script_that_never_calls_run(self):
        self.assertFalse(reload.calls_run("from apkpy_lib import *\nprint(storage.get('x'))\n"))

    def test_a_function_that_is_never_called(self):
        self.assertFalse(reload.calls_run("def main():\n    run()\n"))

    def test_a_file_that_does_not_parse(self):
        self.assertFalse(reload.calls_run("run(\n"))

    def test_apkpy_reload_0_turns_it_off(self):
        for value in ("0", "false", "off", "no"):
            with mock.patch.dict(os.environ, {"APKPY_RELOAD": value}):
                self.assertIsNone(reload._script())

    def test_a_script_run_as_a_module_is_left_alone(self):
        # unittest's own __main__ is a module started with -m.
        with mock.patch.dict(os.environ, {"APKPY_RELOAD": ""}):
            self.assertIsNone(reload._script())


class WhichFilesAreWatchedTests(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="apkpy-reload-test-")
        self.addCleanup(shutil.rmtree, self.folder, True)

    def touch(self, *parts):
        path = os.path.join(self.folder, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write("x = 1\n")
        return path

    def test_the_app_and_the_modules_beside_it(self):
        app = self.touch("writehere.py")
        module = self.touch("screens", "cart.py")
        self.touch("notes.txt")
        self.touch("screens", "deeper", "far.py")
        for skipped in ("__pycache__", ".venv", "venv", "build", "dist"):
            self.touch(skipped, "x.py")
        self.assertEqual(sorted(reload.snapshot(self.folder)), sorted([app, module]))

    def test_a_save_changes_the_snapshot(self):
        app = self.touch("writehere.py")
        before = reload.snapshot(self.folder)
        with open(app, "w") as handle:
            handle.write("x = 22\n")
        self.assertNotEqual(reload.snapshot(self.folder), before)


class WhatAReloadKeepsTests(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="apkpy-reload-test-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        patcher = mock.patch.object(reload, "_child", (self.folder, 2))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.screens = [SimpleNamespace(id=name, _params={})
                        for name in ("login", "home", "profile", "settings")]

    def keep(self, data):
        with open(os.path.join(self.folder, "state.json"), "w", encoding="utf-8") as handle:
            json.dump(data, handle)

    def test_the_screens_open_come_back_in_order_with_their_values(self):
        self.keep({"screens": ["login", "home", "profile"],
                   "params": {"profile": {"user": "Ana"}}})
        behind, top = reload.screens_to_restore(self.screens, self.screens[0])
        self.assertEqual([s.id for s in behind], ["login", "home"])
        self.assertEqual(top.id, "profile")
        self.assertEqual(top._params, {"user": "Ana"})

    def test_a_screen_the_new_code_no_longer_has_starts_over(self):
        self.keep({"screens": ["login", "gone"]})
        self.assertIsNone(reload.screens_to_restore(self.screens, self.screens[0]))

    def test_nothing_kept_yet(self):
        self.assertIsNone(reload.screens_to_restore(self.screens, self.screens[0]))

    def test_outside_a_reload_nothing_is_restored(self):
        self.keep({"screens": ["home"]})
        with mock.patch.object(reload, "_child", None):
            self.assertIsNone(reload.screens_to_restore(self.screens, self.screens[0]))
            self.assertEqual(reload.saved(), {})

    def test_what_the_previewer_hands_over(self):
        from apkpy_lib import ui
        login, home = self.screens[0], self.screens[1]
        home._params = {"from": "login"}
        app = SimpleNamespace(_screen_stack=[login], _active_screen=home, _turned=True)
        self.assertEqual(ui._reload_state(app), {
            "screens": ["login", "home"], "params": {"home": {"from": "login"}},
            "turned": True})

    def test_what_was_typed_and_chosen_comes_back_by_id(self):
        from apkpy_lib import ui

    def fresh_screens(self):
        from apkpy_lib import ui
        before = list(ui._ALL_SCREENS)
        self.addCleanup(lambda: ui._ALL_SCREENS.__setitem__(slice(None), before))
        self.addCleanup(ui._reload_code_values.clear)
        return ui, before

    def test_what_was_typed_and_chosen_comes_back_by_id(self):
        ui, before = self.fresh_screens()

        def build(selected="M"):
            form = ui.Screen(id="reload_form")
            fields = {
                "name": ui.inputs("Name", id="reload_name", screen=form),
                "password": ui.inputs("Password", id="reload_password", type="password",
                                      screen=form),
                "news": ui.inputs("News", id="reload_news", type="switch", screen=form),
                "nameless": ui.inputs("Note", screen=form),
                "size": ui.chips(["S", "M", "L"], selected=selected, id="reload_size",
                                 screen=form),
            }
            tabs = ui.pager(id="reload_tabs", screen=form)
            ui.tab("One", parent=tabs)
            ui.tab("Two", parent=tabs)
            fields["tabs"] = tabs
            ui._reload_note_code_values()        # as run() does, before anything
            return form, fields

        old_form, old = build()
        old["name"].set_value("Ana")
        old["password"].set_value("secret")
        old["news"].set_value("true")
        old["nameless"].set_value("lost")
        old["size"].set_value("L")
        old["tabs"]._current_page = 1
        values = ui._reload_values([old_form])
        self.assertEqual(values, {"reload_form": {
            "reload_name": ["inputs", "Ana", None], "reload_news": ["inputs", "true", None],
            "reload_size": ["chips", "L", "M"], "reload_tabs": ["pager", 1, 0]}})
        self.assertNotIn("secret", json.dumps(values))

        # The new code: same ids, and the screen not drawn yet.
        ui._ALL_SCREENS[:] = before
        new_form, new = build()
        ui._reload_put_back(json.loads(json.dumps(values)))
        self.assertEqual(new["name"]._initial_value, "Ana")
        self.assertEqual(new["news"]._initial_value, "true")
        self.assertIsNone(new["password"]._initial_value)
        self.assertIsNone(new["nameless"]._initial_value)
        self.assertEqual(new["size"].get_value(), "L")
        self.assertEqual(new["tabs"]._initial_page, 1)

        # The code now starts the chips elsewhere: that is the change to see.
        ui._ALL_SCREENS[:] = before
        newer_form, newer = build(selected="S")
        ui._reload_put_back(json.loads(json.dumps(values)))
        self.assertEqual(newer["size"].get_value(), "S")
        self.assertEqual(newer["name"]._initial_value, "Ana")

    def test_a_component_that_changed_kind_starts_over(self):
        ui, before = self.fresh_screens()
        form = ui.Screen(id="reload_kind")
        size = ui.segmented(["S", "M"], selected="S", id="reload_pick", screen=form)
        ui._reload_note_code_values()
        ui._reload_put_back({"reload_kind": {"reload_pick": ["chips", "M", "S"],
                                             "reload_gone": ["inputs", "x", None]}})
        self.assertEqual(size.get_value(), "S")

    def test_the_error_names_the_line_of_the_app(self):
        text = textwrap.dedent('''\
            Traceback (most recent call last):
              File "C:\\apps\\shop\\writehere.py", line 39
                label("Alice",,
                              ^
            SyntaxError: invalid syntax
            ''')
        self.assertEqual(reload._error_line(text),
                         "SyntaxError: invalid syntax\nwritehere.py, line 39")

    def test_the_error_skips_apkpy_s_own_frames(self):
        text = ('Traceback (most recent call last):\n'
                '  File "/home/a/writehere.py", line 12, in <module>\n'
                '  File "/x/apkpy_lib/ui.py", line 900, in label\n'
                'TypeError: label() got an unexpected keyword argument \'colour\'\n')
        self.assertEqual(reload._error_line(text),
                         "TypeError: label() got an unexpected keyword argument 'colour'"
                         "\nwritehere.py, line 12")


class StyleChangeTests(unittest.TestCase):

    BEFORE = 'from apkpy_lib import *\nstyle = """\n#t { color: red; }\n"""\nlabel("Hi", id="t")\n'

    def test_only_the_css_changed(self):
        after = self.BEFORE.replace("red", "blue")
        self.assertEqual(reload.style_change(self.BEFORE, after), "\n#t { color: blue; }\n")

    def test_the_code_changed_too(self):
        after = self.BEFORE.replace("red", "blue").replace('"Hi"', '"Hello"')
        self.assertIsNone(reload.style_change(self.BEFORE, after))

    def test_nothing_changed_but_a_comment(self):
        self.assertIsNone(reload.style_change(self.BEFORE, self.BEFORE + "# note\n"))

    def test_css_built_by_code_is_not_taken_apart(self):
        before = 'size = 10\nstyle = f"#t {{ padding: {size}px; }}"\n'
        self.assertIsNone(reload.style_change(before, before.replace("10", "12")))
        self.assertIsNone(reload.style_change(before, before.replace("padding", "margin")))

    def test_a_file_that_does_not_parse(self):
        self.assertIsNone(reload.style_change(self.BEFORE, self.BEFORE + "label(,\n"))

    def test_style_given_for_the_first_time(self):
        self.assertIsNone(reload.style_change('label("Hi")\n', 'style = "#t {}"\nlabel("Hi")\n'))


# A stand-in for an app: no window, the same protocol. It says it is drawn
# the way child_shown() does, answers new CSS the way its listen() does, and
# waits until the test lets it close.
FAKE_APP = '''
import json, os, sys, time
sys.path.insert(0, {root!r})
from apkpy_lib import reload
folder, generation = reload._child
here = os.path.dirname(os.path.abspath(__file__))
VERSION = {version!r}
style = {style!r}
with open(os.path.join(here, "started-%d" % generation), "w") as handle:
    json.dump({{"pid": os.getpid(), "version": VERSION, "state": folder,
               "argv": sys.argv, "name": __name__}}, handle)
with open(os.path.join(folder, "ready-%d" % generation), "w") as handle:
    handle.write(str(os.getpid()))

def command():
    try:
        with open(os.path.join(folder, "command.json")) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {{}}

heard = command().get("id", 0)
while not os.path.exists(os.path.join(here, "quit")):
    asked = command()
    if asked.get("id", 0) > heard:
        heard = asked["id"]
        with open(os.path.join(here, "styled-%d" % generation), "w") as handle:
            handle.write(asked["style"])
        with open(os.path.join(folder, "command-done.json"), "w") as handle:
            json.dump({{"id": heard, "ok": True}}, handle)
    time.sleep(0.02)
'''


def _alive(pid):
    if sys.platform == "win32":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259                     # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class TheWatcherTests(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="apkpy-reload-app-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.app = os.path.join(self.folder, "writehere.py")
        self.out = io.StringIO()
        # A spare Python finds apkpy_lib the way the app's own Python does.
        env = mock.patch.dict(os.environ, {"APKPY_HEADLESS_CORE": "1",
                                           "PYTHONIOENCODING": "utf-8",
                                           "PYTHONPATH": ROOT})
        env.start()
        self.addCleanup(env.stop)
        self.saves = 0

    def save(self, version, broken=False, style="#t { color: red; }"):
        text = FAKE_APP.format(root=ROOT, version=version, style=style)
        if broken:
            text += "\nlabel(\"Alice\",,\n"
        with open(self.app, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.touch()

    def touch(self):
        # A new mtime even on a file system that keeps whole seconds.
        self.saves += 1
        os.utime(self.app, (time.time(), time.time() + self.saves))

    def started(self, generation, seconds=30):
        path = os.path.join(self.folder, "started-%d" % generation)
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                with open(path) as handle:
                    told = json.load(handle)
                return told["pid"], told["version"], told["state"]
            except (OSError, ValueError):
                pass
            time.sleep(0.02)
        self.fail("generation %d never started:\n%s" % (generation, self.out.getvalue()))

    def told(self, generation):
        with open(os.path.join(self.folder, "started-%d" % generation)) as handle:
            return json.load(handle)

    def wait(self, test, seconds=20):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if test():
                return True
            time.sleep(0.02)
        return False

    def watch(self):
        stop = threading.Event()
        result = {}

        def body():
            result["code"] = reload.supervise(
                self.app, argv=[sys.executable, self.app], out=self.out,
                interval=0.05, stop=stop)

        thread = threading.Thread(target=body)
        thread.start()

        def finish():
            open(os.path.join(self.folder, "quit"), "w").close()
            stop.set()
            thread.join(20)
        self.addCleanup(finish)
        return thread, result

    def test_a_save_replaces_the_app_and_an_error_keeps_the_last_one(self):
        self.save(1)
        thread, result = self.watch()
        first, version, state = self.started(1)
        self.assertEqual(version, 1)

        # A save: the new app starts, then the old one is closed.
        self.save(2)
        second, version, _ = self.started(2)
        self.assertEqual(version, 2)
        self.assertTrue(self.wait(lambda: not _alive(first)), "the old app was left running")
        # Said once the old one is stopped, a moment after it is gone.
        self.assertTrue(self.wait(lambda: "[ApkPy] Reloaded." in self.out.getvalue()),
                        self.out.getvalue())

        # A change that does not start: the running app stays, and is told.
        self.save(3, broken=True)
        error = os.path.join(state, "error.json")
        self.assertTrue(self.wait(lambda: os.path.exists(error)), self.out.getvalue())
        with open(error, encoding="utf-8") as handle:
            told = json.load(handle)
        self.assertEqual(told["generation"], 3)
        self.assertIn("SyntaxError", told["text"])
        self.assertIn("SyntaxError", self.out.getvalue())   # the terminal too
        self.assertTrue(_alive(second))

        # The fix: a new app, and the error is gone.
        self.save(4)
        self.started(4)
        self.assertTrue(self.wait(lambda: not os.path.exists(error)))
        self.assertTrue(self.wait(lambda: not _alive(second)))

        # Closing the app ends the watching, with the app's exit code.
        open(os.path.join(self.folder, "quit"), "w").close()
        thread.join(20)
        self.assertEqual(result.get("code"), 0)
        self.assertFalse(os.path.exists(state), "the state folder was left behind")

    def test_an_app_that_does_not_start_waits_for_the_next_save(self):
        self.save(1, broken=True)
        thread, result = self.watch()
        self.assertTrue(self.wait(lambda: "did not start" in self.out.getvalue()),
                        self.out.getvalue())
        self.save(2)
        self.started(2)
        open(os.path.join(self.folder, "quit"), "w").close()
        thread.join(20)
        self.assertEqual(result.get("code"), 0)

    def test_a_save_that_changes_only_the_css_goes_to_the_open_app(self):
        self.save(1)
        thread, result = self.watch()
        first, _, state = self.started(1)
        self.save(1, style="#t { color: blue; }")
        styled = os.path.join(self.folder, "styled-1")
        self.assertTrue(self.wait(lambda: os.path.exists(styled)), self.out.getvalue())
        with open(styled) as handle:
            self.assertEqual(handle.read(), "#t { color: blue; }")
        self.assertTrue(self.wait(lambda: "New CSS applied." in self.out.getvalue()))
        time.sleep(0.5)
        self.assertFalse(any(name.startswith("started-") and name != "started-1"
                             for name in os.listdir(self.folder)), "the app was started again")
        self.assertTrue(_alive(first))

        # Code and CSS together: the app starts again, with both.
        self.save(2, style="#t { color: green; }")
        self.assertTrue(self.wait(lambda: not _alive(first)), self.out.getvalue())

    def test_a_save_runs_in_the_python_kept_ready(self):
        self.save(1)
        thread, result = self.watch()
        _, _, state = self.started(1)
        # The spare is loaded before the save, as it is while someone types.
        spare = os.path.join(state, "spare-2")
        self.assertTrue(self.wait(lambda: os.path.exists(spare)), self.out.getvalue())
        with open(spare) as handle:
            spare_pid = int(handle.read())
        self.save(2)
        pid, version, _ = self.started(2)
        self.assertEqual((pid, version), (spare_pid, 2))
        told = self.told(2)
        # What the app's own code sees is what python writehere.py gives it.
        self.assertEqual(told["name"], "__main__")
        self.assertEqual([os.path.abspath(part) for part in told["argv"]], [self.app])

    def test_a_save_before_the_spare_has_loaded_still_uses_it(self):
        self.save(1)
        thread, result = self.watch()
        self.started(1)
        self.save(2)
        self.save(3)
        _, version, _ = self.started(2)
        self.assertEqual(version, 3)

    def test_a_change_to_apkpy_itself_starts_a_fresh_python(self):
        # Working on ApkPy with the app beside it: the spare has the old
        # engine loaded, so a save of the engine starts from nothing.
        engine = os.path.join(self.folder, "engine")
        os.makedirs(engine)
        patch = mock.patch.object(reload, "__file__", os.path.join(engine, "reload.py"))
        patch.start()
        self.addCleanup(patch.stop)
        self.save(1)
        thread, result = self.watch()
        _, _, state = self.started(1)
        self.assertTrue(self.wait(lambda: os.path.exists(os.path.join(state, "spare-2"))),
                        self.out.getvalue())
        with open(os.path.join(engine, "ui.py"), "w") as handle:
            handle.write("x = 1\n")
        _, version, _ = self.started(3)
        self.assertEqual(version, 1)
        self.assertFalse(os.path.exists(os.path.join(self.folder, "started-2")))

    def test_saving_the_same_text_again_starts_nothing(self):
        self.save(1)
        thread, result = self.watch()
        first, _, _ = self.started(1)
        self.touch()
        time.sleep(1.0)
        self.assertNotIn("Reloaded.", self.out.getvalue())
        self.assertFalse(os.path.exists(os.path.join(self.folder, "started-2")))
        self.assertTrue(_alive(first))

    def test_the_app_ends_when_the_watcher_is_killed(self):
        # python writehere.py itself: importing apkpy_lib makes that Python
        # the watcher. An IDE's Stop button kills it without a word; the app
        # it started must notice and end, not stay behind on its own.
        os.environ.pop("APKPY_HEADLESS_CORE", None)
        with open(self.app, "w", encoding="utf-8") as handle:
            handle.write(textwrap.dedent('''\
                import os, sys, time
                sys.path.insert(0, %r)
                from apkpy_lib import reload
                here = os.path.dirname(os.path.abspath(__file__))

                def run():
                    with open(os.path.join(here, "started"), "w") as handle:
                        handle.write(str(os.getpid()))
                    while not reload._watcher_gone():
                        time.sleep(0.05)
                    open(os.path.join(here, "noticed"), "w").close()

                if __name__ == "__main__":
                    run()
                ''' % ROOT))
        watcher = subprocess.Popen([sys.executable, self.app], cwd=self.folder,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.addCleanup(lambda: watcher.poll() is None and watcher.kill())
        started = os.path.join(self.folder, "started")
        self.assertTrue(self.wait(lambda: os.path.exists(started)
                                  and open(started).read(), 60), "the app never started")
        app_pid = int(open(started).read())
        self.assertNotEqual(app_pid, watcher.pid)
        watcher.kill()
        watcher.wait(20)
        self.assertTrue(self.wait(lambda: os.path.exists(os.path.join(self.folder, "noticed"))),
                        "the app did not notice that the watcher was gone")
        self.assertTrue(self.wait(lambda: not _alive(app_pid)))

    def test_a_python_the_app_starts_is_not_taken_for_a_reload(self):
        # The app's own Python takes the reload's variables out of its
        # environment, and only a Python the watcher started takes them.
        env = dict(os.environ, APKPY_RELOAD_DIR=self.folder, APKPY_RELOAD_GEN="2",
                   APKPY_RELOAD_PARENT="1")
        code = ("import sys; sys.path.insert(0, %r); from apkpy_lib import reload; "
                "print(reload.child())" % ROOT)
        done = subprocess.run([sys.executable, "-c", code], env=env,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.stdout.strip(), "False", done.stderr)


if __name__ == "__main__":
    unittest.main()
