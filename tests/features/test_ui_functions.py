# -*- coding: utf-8 -*-
"""A function that builds UI, written once and called on several screens.

The Previewer runs it as Python. The compiler refused it (U2033 on the label()
inside the function), so a header on five screens was written five times. And
a module-level `for page, title in [...]:` that built UI was dropped without a
word: four published showcase apps had screens with nothing on them on the
phone -- the tracks of a playlist, the title and copy of three tabs each.

Now each module-level call of a UI function is replaced by its body before
anything is translated, and a module-level loop that builds UI is unrolled.
Pinned here: what that expansion produces, what it refuses (U2038) and why,
and -- the point of it all -- that the Previewer running the same Python and
the phone's layouts end up with the same components on the same screens.
"""

import os
import re
import shutil
import tempfile
import unittest

import apkpy_lib as api
from apkpy_lib.core.compiler import translate_python_to_android

APP = '''from apkpy_lib import *
home = Screen(id="uif_home")
profile = Screen(id="uif_profile")

def go_home():
    on_click_navigate(home)

def header(title, screen, back="Back"):
    label(title, id="title", screen=screen)
    button(back, id="back_" + screen.id, screen=screen, command=go_home)

def stat(name, value, screen):
    box = card(id="stat", screen=screen)
    label(name, id="stat_name", parent=box)
    number = label(value, id="stat_value", parent=box)
    return number

def page(title, screen):
    header(title, screen)
    label(f"on {screen.id}", id="footer", screen=screen)

STATS = [{"name": "Steps", "value": "8 000"}, {"name": "Sleep", "value": "7 h"}]

page("Home", home)
page("Profile", profile)
visits = stat("Visits", "12", home)
for s in STATS:
    stat(s["name"], s["value"], profile)
for i in range(3):
    label("Row " + str(i), id="row", screen=home)
for screen, title in [(home, "Tip A"), (profile, "Tip B")]:
    label(title, id="tip", screen=screen)

def bump():
    visits.set_value("13")

button("Bump", id="bump", screen=home, command=bump)
run(start_screen=home)
'''

HOME_TEXTS = ["Home", "Back", "on uif_home", "Visits", "12", "Row 0", "Row 1",
              "Row 2", "Tip A", "Bump"]
PROFILE_TEXTS = ["Profile", "Back", "on uif_profile", "Steps", "8 000", "Sleep",
                 "7 h", "Tip B"]


def _layout_texts(files, screen_id):
    xml = files["res/layout/activity_screen_%s.xml" % screen_id]
    return re.findall(r'android:text="([^"]*)"', xml)


def _refusal(source):
    files = translate_python_to_android(source)
    error = files.get("error.txt", "")
    if not error:
        raise AssertionError("the build went through")
    return error


BASE = ('from apkpy_lib import *\nhome = Screen(id="home")\n'
        'def header(t, screen):\n    label(t, screen=screen)\n')


class TheCompilerExpandsTheCall(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = translate_python_to_android(APP)
        if "error.txt" in cls.files:
            raise AssertionError(cls.files["error.txt"][:800])

    def test_each_screen_gets_its_own_copy(self):
        self.assertEqual(_layout_texts(self.files, "uif_home"), HOME_TEXTS)
        self.assertEqual(_layout_texts(self.files, "uif_profile"), PROFILE_TEXTS)

    def test_a_returned_component_answers_to_its_name(self):
        activity = self.files["java/Screen_uif_homeActivity.java"]
        body = activity[activity.index("pythonCallback_bump()"):]
        body = body[:body.index("\n    }")]
        # Home, on uif_home, Visits, 12: the fourth label on the screen.
        self.assertIn("findViewById(R.id.lbl4)).setText(String.valueOf(\"13\"))", body)

    def test_the_function_is_gone_from_the_java(self):
        java = "\n".join(v for k, v in self.files.items() if k.endswith(".java"))
        self.assertNotIn("pythonCallback_header", java)
        self.assertNotIn("pythonCallback_stat", java)


class TheLoopsTheShowcasesUsed(unittest.TestCase):
    """The shape of the published showcase apps, which lost these rows."""

    def test_unpacking_a_list_of_tuples(self):
        source = ('from apkpy_lib import *\nhome = Screen(id="home")\n'
                  'queue = container(id="queue", screen=home)\n'
                  'for number, title in [("01", "Soft Static"), ("02", "Glass District")]:\n'
                  '    track = container(id="track_" + number, parent=queue)\n'
                  '    label(number, id="no_" + number, parent=track)\n'
                  '    label(title, id="title_" + number, parent=track)\n'
                  'run(start_screen=home)\n')
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:400])
        self.assertEqual(_layout_texts(files, "home"),
                         ["01", "Soft Static", "02", "Glass District"])

    def test_a_loop_that_builds_nothing_and_unpacks_is_refused(self):
        error = _refusal('from apkpy_lib import *\nhome = Screen(id="home")\n'
                         'for a, b in [("1", "2")]:\n    storage.set(a, b)\n'
                         'run(start_screen=home)\n')
        self.assertIn("U2033", error)
        self.assertIn("Unpacking in a for loop", error)


class ItRefusesWhatThePhoneCannotHonour(unittest.TestCase):

    def assertRefused(self, source, *needles):
        error = _refusal(source)
        self.assertIn("U2038", error)
        for needle in needles:
            self.assertIn(needle, error)

    def test_called_from_a_tap(self):
        self.assertRefused(BASE + 'button("x", screen=home, command=lambda: header("a", home))\n'
                           'run(start_screen=home)\n', "header() builds UI")

    def test_called_from_another_function(self):
        self.assertRefused(BASE + 'def later():\n    header("a", home)\n'
                           'button("x", screen=home, command=later)\nrun(start_screen=home)\n',
                           "it calls header()")

    def test_bound_to_a_name_when_it_returns_nothing(self):
        self.assertRefused(BASE + 't = header("a", home)\nrun(start_screen=home)\n',
                           "returns nothing")

    def test_a_loop_over_what_arrives_later(self):
        self.assertRefused(BASE + 'for r in db.query("SELECT 1"):\n    header("a", home)\n'
                           'run(start_screen=home)\n', "list_view()")

    def test_recursion(self):
        self.assertRefused('from apkpy_lib import *\nhome = Screen(id="home")\n'
                           'def f(screen):\n    label("x", screen=screen)\n    f(screen)\n'
                           'f(home)\nrun(start_screen=home)\n', "calls itself")

    def test_a_missing_argument(self):
        self.assertRefused(BASE + 'header("a")\nrun(start_screen=home)\n', "missing the argument")

    def test_a_return_in_the_middle(self):
        self.assertRefused('from apkpy_lib import *\nhome = Screen(id="home")\n'
                           'def f(screen):\n    x = label("a", screen=screen)\n    return x\n'
                           '    label("b", screen=screen)\nf(home)\nrun(start_screen=home)\n',
                           "returns before its end")

    def test_the_error_points_at_the_line_that_was_written(self):
        error = _refusal(BASE + 'button("x", screen=home, command=lambda: header("a", home))\n'
                         'run(start_screen=home)\n')
        self.assertIn("writehere.py:5", error)


class TheArgumentsAreBoundLikePython(unittest.TestCase):

    def test_defaults_keywords_and_a_shadowing_lambda(self):
        source = ('from apkpy_lib import *\nhome = Screen(id="home")\n'
                  'def item(text, screen, suffix="!"):\n'
                  '    label(text + suffix, screen=screen)\n'
                  '    button("go", screen=screen, command=lambda text="x": toast(text))\n'
                  'item("a", home)\nitem(screen=home, text="b", suffix="?")\n'
                  'run(start_screen=home)\n')
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:400])
        self.assertEqual(_layout_texts(files, "home"), ["a!", "go", "b?", "go"])


class AHelperFileCanHoldUI(unittest.TestCase):
    """1.10.0 let a helper hold functions and constants. Now UI too."""

    def test_widgets_from_a_helper(self):
        folder = tempfile.mkdtemp(prefix="apkpy-uif-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        with open(os.path.join(folder, "widgets.py"), "w", encoding="utf-8") as f:
            f.write('from apkpy_lib import *\n\n'
                    'def header(title, screen):\n'
                    '    label(title, id="title", screen=screen)\n')
        source = ('from apkpy_lib import *\nimport widgets\n'
                  'home = Screen(id="home")\nother = Screen(id="other")\n'
                  'widgets.header("Home", home)\nwidgets.header("Other", other)\n'
                  'run(start_screen=home)\n')
        with open(os.path.join(folder, "writehere.py"), "w", encoding="utf-8") as f:
            f.write(source)
        files = translate_python_to_android(
            source, source_name=os.path.join(folder, "writehere.py"), project_root=folder)
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:600])
        self.assertEqual(_layout_texts(files, "home"), ["Home"])
        self.assertEqual(_layout_texts(files, "other"), ["Other"])


def _preview_texts(component):
    texts = []
    text = component.kwargs.get("text")
    if isinstance(text, str):
        texts.append(text)
    for child in getattr(component, "children", []) or []:
        texts.extend(_preview_texts(child))
    return texts


class ThePreviewerEndsUpWithTheSameScreens(unittest.TestCase):
    """The Previewer runs the Python as written; the phone gets the expansion.
    Both have to put the same components on the same screens."""

    def test_same_texts_on_each_screen(self):
        namespace = {"__name__": "uif_preview"}
        exec(compile(APP.replace("run(start_screen=home)\n", ""), "writehere.py", "exec"),
             namespace)
        for screen_name, expected in (("home", HOME_TEXTS), ("profile", PROFILE_TEXTS)):
            screen = namespace[screen_name]
            texts = []
            for component in screen.components:
                texts.extend(_preview_texts(component))
            with self.subTest(screen=screen_name):
                self.assertEqual(texts, expected)


if __name__ == "__main__":
    unittest.main()
