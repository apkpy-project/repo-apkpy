"""int() and float() of a text say what Python says.

int("x") on the phone was Java's NumberFormatException, 'For input string:
"x"': in a crash, in apkpy logs, and in str(e) of an except ValueError. A
Python person reads "invalid literal for int() with base 10: 'x'". The text
is now read by ApkpyValues.toInt / toFloat, which take what Python takes
(spaces around, _ between digits, 0x with base 16 or 0) and refuse what it
refuses (1.5f and 0x1p3, which Java's parseDouble took).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from apkpy_lib.core.compiler import translate_python_to_android  # noqa: E402

from test_classes import HEAD, _cpython, _generated  # noqa: E402
from test_data_rules import TOOLING  # noqa: E402

APP = HEAD + '''

def as_int():
    try:
        out.set_value(str(int(field.get_value())))
    except ValueError as e:
        out.set_value("ValueError: " + str(e))


def in_base():
    try:
        out.set_value(str(int(field.get_value(), 16)) + " " + str(int(field.get_value(), 0)))
    except ValueError as e:
        out.set_value("ValueError: " + str(e))


def as_float():
    try:
        out.set_value(str(float(field.get_value())))
    except ValueError as e:
        out.set_value("ValueError: " + str(e))


button("1", id="b1", command=as_int, screen=home)
button("2", id="b2", command=in_base, screen=home)
button("3", id="b3", command=as_float, screen=home)
'''

TYPED = [
    "x", "", " 12 ", "+7", "-0", "1_000", "1__0", "_1", "1_", "0x1f", "0X_1F", "-0x1f",
    "0o17", "0b101", "010", "00", "it's", 'say "hi"', "tab\there", "x" * 300,
    "1.5", "1.5f", "0x1p3", " 2.5 ", ".5", "5.", "1e3", "1_0.5", "nan", "-Infinity", "inf",
    "ff", "12 34",
]
# Unicode digits (int("٣") is 3) are read by Java's parseLong too, but the
# harness hands the text over on the command line, which Windows makes "?".


class TheTextIsReadAsPythonReadsIt(unittest.TestCase):

    def test_the_same_answers_and_errors_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        want = _cpython(APP, TYPED)
        got = _generated(APP, TYPED)
        for i, (w, g) in enumerate(zip(want, got)):
            self.assertEqual(w, g, "typed %r, button %d" % (TYPED[i // 3], i % 3 + 1))
        self.assertEqual(len(want), len(got))


class TheJava(unittest.TestCase):

    def _java(self, body):
        files = translate_python_to_android(
            HEAD + "\n\ndef go():\n" + body + '\n\nbutton("Go", id="b1", command=go, screen=home)\n')
        return files["java/Screen_homeActivity.java"], files["java/ApkpyValues.java"]

    def test_int_of_a_text_is_read_by_apkpy_values(self):
        java, _ = self._java("    out.set_value(str(int(field.get_value()) + 1))")
        self.assertIn("ApkpyValues.toInt(String.valueOf(", java)
        self.assertNotIn("Long.parseLong(String.valueOf(t).trim())", java)

    def test_int_of_a_number_is_still_a_cast(self):
        java, _ = self._java("    out.set_value(str(int(2.5 * 3)))")
        self.assertIn("_apkpyTrunc(", java)
        self.assertNotIn("ApkpyValues.toInt(", java)

    def test_the_message_is_pythons_in_the_class(self):
        _, values = self._java("    out.set_value(str(int(field.get_value())))")
        self.assertIn('"invalid literal for int() with base " + base + ": " + shown', values)
        self.assertIn('"could not convert string to float: " + repr(text)', values)

    def test_each_screen_shares_one_repr(self):
        java, values = self._java('    t = field.get_value()\n    out.set_value(f"{t!r}")')
        self.assertIn("return ApkpyValues.repr(s);", java)
        self.assertIn("public static String repr(String s)", values)


if __name__ == "__main__":
    unittest.main()
