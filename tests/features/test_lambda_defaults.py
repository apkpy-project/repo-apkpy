# -*- coding: utf-8 -*-
"""`lambda t=target: ...` -- the Python way to give each button of a loop its
own value.

The compiler read a lambda's parameters and never its defaults, so `t` reached
the Java as a name nothing declared. `on_click_navigate(t)` was dropped without
a word: a menu of six buttons, built by a loop, did nothing on a phone while
the Previewer opened every screen. `toast(c)` became `String.valueOf(c)` and
javac stopped the build on generated code (B5005). Found rebuilding six
well-known screens (the "replicas") on 25-09-2026.

Now each default is written into the lambda's body before translation. That is
exact for a value that cannot change before the tap -- a literal, a name bound
once -- and anything else is refused with U2039 rather than translated into
something Python would not do.
"""

import ast
import re
import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import lambda_defaults


def _bound(source):
    return ast.unparse(lambda_defaults.bind(ast.parse(source)))


def _callback(java, name):
    match = re.search(r"private void pythonCallback_%s_cmd\(\) \{(.*?)\n    \}" % name,
                      java, re.S)
    return " ".join(match.group(1).split()) if match else None


MENU = '''from apkpy_lib import *
home = Screen(id="home")
camera = Screen(id="camera")
chat = Screen(id="chat")
for target, name in [(camera, "Camera"), (chat, "Chat")]:
    button(name, id="open_" + target.id, screen=home,
           command=lambda t=target: on_click_navigate(t))
for key, count in [("likes", "12.4K"), ("comments", "318")]:
    button(count, id="count_" + key, screen=camera,
           command=lambda c=count: toast(c))
label("", id="spacer", screen=chat)
run(start_screen=home)
'''


class EachButtonKeepsItsOwnValue(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = translate_python_to_android(MENU)
        if "error.txt" in cls.files:
            raise AssertionError(cls.files["error.txt"][:800])
        cls.home = cls.files["java/Screen_homeActivity.java"]
        cls.camera = cls.files["java/Screen_cameraActivity.java"]

    def test_each_menu_button_opens_its_own_screen(self):
        self.assertIn("Screen_cameraActivity.class", _callback(self.home, "open_camera"))
        self.assertIn("Screen_chatActivity.class", _callback(self.home, "open_chat"))

    def test_the_buttons_are_wired(self):
        # An empty callback left the button without a listener at all.
        self.assertEqual(self.home.count("setOnClickListener"), 2)

    def test_a_toast_reads_the_value_of_its_turn(self):
        self.assertIn('String.valueOf("12.4K")', _callback(self.camera, "count_likes"))
        self.assertIn('String.valueOf("318")', _callback(self.camera, "count_comments"))

    def test_no_java_reads_the_parameter_name(self):
        java = "".join(v for k, v in self.files.items() if k.endswith(".java"))
        self.assertNotRegex(java, r"String\.valueOf\([ct]\)")


# These read the rewritten module back as text, with ast.unparse(): Python
# 3.9 and later. What the rewrite does to the app is checked on every
# version by the classes around this one.
@unittest.skipUnless(hasattr(ast, "unparse"), "ast.unparse() is Python 3.9 and later")
class TheDefaultIsWrittenIntoTheBody(unittest.TestCase):

    def test_a_literal(self):
        self.assertEqual(_bound('f = lambda msg="Hi": toast(msg)'),
                         "f = lambda: toast('Hi')")

    def test_a_parameter_without_a_default_stays(self):
        self.assertEqual(_bound("home = 1\nf = lambda item, s=home: go(s, item)"),
                         "home = 1\nf = lambda item: go(home, item)")

    def test_a_keyword_only_default(self):
        self.assertEqual(_bound("f = lambda *, n=3: show(n)"), "f = lambda: show(3)")

    def test_a_nested_lambda_that_rebinds_the_name_is_left_alone(self):
        self.assertEqual(_bound("f = lambda x=1: g(x, lambda x: x)"),
                         "f = lambda: g(1, lambda x: x)")

    def test_a_comprehension_that_rebinds_the_name_is_left_alone(self):
        self.assertEqual(_bound("f = lambda x=2: [x for x in rows]"),
                         "f = lambda: [x for x in rows]")

    def test_a_lambda_without_defaults_is_untouched(self):
        self.assertEqual(_bound("f = lambda item: toast(item)"), "f = lambda item: toast(item)")

    def test_a_function_parameter_bound_once(self):
        source = "def build(name):\n    return lambda n=name: toast(n)"
        self.assertIn("lambda: toast(name)", _bound(source))


class AValueThatCanChangeIsRefused(unittest.TestCase):

    def assertRefused(self, source, *needles):
        from apkpy_lib.diagnostics import ApkpyError
        with self.assertRaises(ApkpyError) as caught:
            lambda_defaults.bind(ast.parse(source))
        text = str(caught.exception) + " " + getattr(caught.exception, "cause", "")
        self.assertEqual(getattr(caught.exception, "code", ""), "U2039")
        for needle in needles:
            self.assertIn(needle, text)

    def test_a_name_assigned_again(self):
        self.assertRefused("n = 1\nf = lambda v=n: toast(v)\nn = 2", "bound more than once")

    def test_a_loop_that_stays_a_loop(self):
        self.assertRefused("for c in rows:\n    handlers.append(lambda v=c: toast(v))",
                           "bound more than once")

    def test_a_name_a_function_changes(self):
        self.assertRefused("n = 1\ndef bump():\n    global n\n    n = 2\n"
                           "f = lambda v=n: toast(v)", "global")

    def test_a_computed_default(self):
        self.assertRefused("f = lambda v=a + b: toast(v)", "computed")

    def test_the_build_names_the_code(self):
        source = ('from apkpy_lib import *\nhome = Screen(id="home")\nlabel_text = "a"\n'
                  'button("x", screen=home, command=lambda v=label_text: toast(v))\n'
                  'label_text = "b"\nrun(start_screen=home)\n')
        error = translate_python_to_android(source).get("error.txt", "")
        self.assertIn("U2039", error)


if __name__ == "__main__":
    unittest.main()
