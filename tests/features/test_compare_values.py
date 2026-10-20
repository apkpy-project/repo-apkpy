# -*- coding: utf-8 -*-
"""A comparison whose right side is not written out.

    if a == b:                              while i < n:
    if first.get_value() == second.get_value():

Until 1.13.0 the first and the third were built as ``a.equals("")`` -- the
right side read as nothing, without a word -- and the second compared two
numbers as text, so a loop to 12 stopped at 2 ("2" sorts after "12"). The
Previewer runs Python and was right every time, which is how it went unseen:
every example compared against something written in the source.

What is held here: a right side that is a name, a call or a sum reaches the
Java; two values ApkPy knows are numbers are compared as numbers; and the
Java that comes out answers what Python answers.
"""

import io
import os
import re
import subprocess
import tempfile
import unittest

from apkpy_lib.core.compiler import translate_python_to_android

from test_data_rules import TOOLING
from test_kit import needs_sdk

HEAD = ('from apkpy_lib import *\n'
        'home = Screen(id="home")\n'
        'out = label("", id="out", screen=home)\n'
        'first = inputs("First", id="first", screen=home)\n'
        'second = inputs("Second", id="second", screen=home)\n'
        'LIMIT = 10\n\n')
TAIL = '\nbutton("Go", id="go", screen=home, command=go)\nrun(start_screen=home)\n'


def _java(body, top=""):
    lines = "\n".join("    " + line for line in body.split("\n"))
    files = translate_python_to_android(HEAD + top + "def go():\n" + lines + "\n" + TAIL)
    if "error.txt" in files:
        raise AssertionError(files["error.txt"][:900])
    return files["java/Screen_homeActivity.java"]


def _test_of(java, opener="if ("):
    """The condition of the if (or while) that guards the toast."""
    lines = java.splitlines()
    for index, line in enumerate(lines[:-1]):
        stripped = line.strip()
        if stripped.startswith(opener) and (
                "Toast.makeText" in lines[index + 1] or "i = " in lines[index + 1]):
            return stripped
    raise AssertionError("no such condition in the Java")


def _if(body, top=""):
    return _test_of(_java(body, top))


class TextAgainstText(unittest.TestCase):
    """Two values that are text are compared as Python compares two strings."""

    def test_two_names(self):
        line = _if('a = first.get_value()\nb = second.get_value()\nif a == b:\n    toast("hit")')
        self.assertEqual(line, "if (a.equals(String.valueOf(b))) {")
        line = _if('a = first.get_value()\nb = second.get_value()\nif a != b:\n    toast("hit")')
        self.assertEqual(line, "if (!a.equals(String.valueOf(b))) {")

    def test_two_fields(self):
        line = _if('if first.get_value() == second.get_value():\n    toast("hit")')
        self.assertIn("R.id.inp1", line)
        self.assertIn(".equals(String.valueOf(", line)
        self.assertIn("R.id.inp2", line)

    def test_which_comes_first(self):
        line = _if('a = first.get_value()\nb = second.get_value()\nif a < b:\n    toast("hit")')
        self.assertEqual(line, "if (String.valueOf(a).compareTo(String.valueOf(b)) < 0) {")

    def test_a_call_to_the_phone_against_a_name(self):
        line = _if('text = first.get_value()\nif files.read("a.txt") == text:\n    toast("hit")')
        self.assertIn("_apkpyNative_files_read(", line)
        self.assertTrue(line.endswith(".equals(String.valueOf(text))) {"), line)

    def test_a_record_against_a_name(self):
        line = _if('want = first.get_value()\nrow = {"name": "x"}\n'
                   'if row["name"] == want:\n    toast("hit")')
        self.assertTrue(line.endswith('.equals(String.valueOf(want))) {'), line)

    def test_at_the_top_of_the_file(self):
        java = _java('toast("x")', top='A = storage.get("a", "")\nB = storage.get("b", "")\n'
                                       'if A == B:\n    out.set_value("same")\n\n')
        self.assertIn("if (A.equals(String.valueOf(B))) {", java)


class NumbersAgainstNumbers(unittest.TestCase):
    """A side ApkPy knows is a number makes it a comparison of numbers."""

    NUMBER = "(Long.parseLong(String.valueOf(%s)))"

    def test_two_names(self):
        for op in ("==", "!=", "<", ">", "<=", ">="):
            line = _if('n = 3\nm = 4\nif n %s m:\n    toast("hit")' % op)
            self.assertEqual(line, "if (%s %s %s) {" % (self.NUMBER % "n", op, self.NUMBER % "m"))

    def test_a_loop_counts_to_its_end(self):
        java = _java('i = 0\nn = 12\nwhile i < n:\n    i += 1\ntoast(str(i))')
        line = _test_of(java, "while (")
        self.assertIn("%s < %s" % (self.NUMBER % "i", self.NUMBER % "n"), line)
        self.assertNotIn("compareTo", line)

    def test_a_number_below_zero_is_a_number(self):
        line = _if('n = 3\nif n > -1:\n    toast("hit")')
        self.assertEqual(line, "if (%s > ((-1))) {" % (self.NUMBER % "n"))

    def test_a_number_kept_at_the_top_of_the_file(self):
        line = _if('n = int(first.get_value())\nif n > LIMIT:\n    toast("hit")')
        self.assertEqual(line, "if (%s > %s) {" % (self.NUMBER % "n", self.NUMBER % "LIMIT"))

    def test_sums(self):
        line = _if('n = 3\nm = 4\nif n + 1 > m * 2:\n    toast("hit")')
        self.assertIn("Math.addExact((long)(Long.parseLong(String.valueOf(n))), (long)(1))", line)
        self.assertIn("Math.multiplyExact((long)(Long.parseLong(String.valueOf(m))), (long)(2))", line)
        self.assertNotIn("compareTo", line)

    def test_text_made_a_number_on_both_sides(self):
        line = _if('if int(first.get_value()) > int(second.get_value()):\n    toast("hit")')
        self.assertEqual(line.count("Long.parseLong("), 2)
        self.assertNotIn("compareTo", line)

    def test_one_side_known_is_enough(self):
        # len() and a name that is a number; text from a field and a number.
        line = _if('m = 4\nif len(first.get_value()) >= m:\n    toast("hit")')
        self.assertIn(">= %s" % (self.NUMBER % "m"), line)
        self.assertIn("_apkpyTextLen(", line)
        line = _if('total = 2.5\nif total == float(first.get_value()):\n    toast("hit")')
        self.assertEqual(line.count("Double.parseDouble("), 2)

    def test_in_a_value_and_in_a_longer_condition(self):
        java = _java('n = 3\nm = 4\nword = "big" if n > m else "small"\ntoast(word)')
        self.assertIn("%s > %s ? " % (self.NUMBER % "n", self.NUMBER % "m"), java)
        line = _if('n = 3\nm = 4\nif n > m or n == 0:\n    toast("hit")')
        self.assertIn("%s > %s" % (self.NUMBER % "n", self.NUMBER % "m"), line)


class WrittenOut(unittest.TestCase):
    """Against a value written in the source nothing changed."""

    def test_text(self):
        line = _if('a = first.get_value()\nif a == "abc":\n    toast("hit")')
        self.assertEqual(line, 'if (a.equals("abc")) {')
        line = _if('a = first.get_value()\nif a == "":\n    toast("hit")')
        self.assertEqual(line, 'if (a.equals("")) {')

    def test_a_number(self):
        line = _if('n = 3\nif n >= 3:\n    toast("hit")')
        self.assertEqual(line, "if (Double.parseDouble(String.valueOf(n)) >= 3) {")


class NothingIsReadAsNothing(unittest.TestCase):
    """The mistake itself: a right side that reached the Java as ""."""

    FORMS = [
        'a = first.get_value()\nb = second.get_value()\nif a == b:\n    toast("hit")',
        'a = first.get_value()\nb = second.get_value()\nif a >= b:\n    toast("hit")',
        'if first.get_value() != second.get_value():\n    toast("hit")',
        'a = first.get_value()\nif a == second.get_value():\n    toast("hit")',
        'a = first.get_value()\nif a == second.get_value() + "!":\n    toast("hit")',
        'n = 3\na = first.get_value()\nif a == str(n):\n    toast("hit")',
        'n = 3\nm = 4\nif n > m:\n    toast("hit")',
        'n = 3\nif n > LIMIT:\n    toast("hit")',
        'n = 3\nif n > -1:\n    toast("hit")',
        'k = 2\nfor i in range(5):\n    if i == k:\n        toast("hit")',
        'want = "ok"\nif haptics.tap() == want:\n    toast("hit")',
        'want = "ok"\nif storage.get("k", "") == want:\n    toast("hit")',
    ]

    def test_no_right_side_is_empty(self):
        for body in self.FORMS:
            line = _if(body)
            self.assertNotIn('equals("")', line, body)
            self.assertNotIn('compareTo("")', line, body)

    def test_a_function_called_with_two_values(self):
        java = _java('same(first.get_value(), second.get_value())',
                     top='def same(a, b):\n    if a == b:\n        toast("hit")\n\n')
        self.assertIn("if (a.equals(String.valueOf(b))) {", java)


@needs_sdk
class TheJavaAnswersWhatPythonAnswers(unittest.TestCase):
    """The conditions, run. Every value on the phone is text, so each name is
    a String holding what the Python name holds."""

    CASES = [
        # (the lines before the if, the test, {name: value as text}, Python's answer)
        ('i = 0\nn = 0', "i < n", {"i": "2", "n": "12"}, True),
        ('i = 0\nn = 0', "i < n", {"i": "12", "n": "12"}, False),
        ('i = 0\nn = 0', "i >= n", {"i": "100", "n": "99"}, True),
        ('n = 0\nm = 0', "n == m", {"n": "3", "m": "3"}, True),
        ('n = 0\nm = 0', "n != m", {"n": "3", "m": "4"}, True),
        ('n = 0\nm = 0', "n + 1 > m * 2", {"n": "9", "m": "4"}, True),
        ('n = 0', "n > -1", {"n": "0"}, True),
        ('n = 0', "n > -1", {"n": "-5"}, False),
        ('a = first.get_value()\nb = second.get_value()', "a == b",
         {"a": "Lisbon", "b": "Lisbon"}, True),
        ('a = first.get_value()\nb = second.get_value()', "a == b",
         {"a": "Lisbon", "b": "Porto"}, False),
        ('a = first.get_value()\nb = second.get_value()', "a != b",
         {"a": "Lisbon", "b": "Porto"}, True),
        ('a = first.get_value()\nb = second.get_value()', "a < b",
         {"a": "apple", "b": "banana"}, True),
        ('a = first.get_value()\nb = second.get_value()', "a < b",
         {"a": "pear", "b": "banana"}, False),
    ]

    def test_them(self):
        blocks = []
        for index, (before, test, values, _wanted) in enumerate(self.CASES):
            line = _if('%s\nif %s:\n    toast("hit")' % (before, test))
            found = re.fullmatch(r"if \((.*)\) \{", line)
            self.assertIsNotNone(found, line)
            names = "".join('String %s = "%s"; ' % pair for pair in sorted(values.items()))
            blocks.append('{ %sSystem.out.println("%d|" + (%s)); }' % (names, index, found.group(1)))
        if not TOOLING:
            self.skipTest("no JDK on this machine")
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-compare-")
        with io.open(os.path.join(work, "Harness.java"), "w", encoding="utf-8") as handle:
            handle.write("public class Harness {\n    public static void main(String[] argv) {\n        "
                         + "\n        ".join(blocks) + "\n    }\n}\n")
        built = subprocess.run([javac, "-encoding", "UTF-8", "-d", work,
                                os.path.join(work, "Harness.java")],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java_bin, "-cp", work, "Harness"], capture_output=True, text=True)
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)
        answers = dict(line.split("|", 1) for line in ran.stdout.splitlines())
        self.assertEqual(len(answers), len(self.CASES))
        for index, (before, test, values, wanted) in enumerate(self.CASES):
            self.assertEqual(answers[str(index)], "true" if wanted else "false",
                             "%s with %r" % (test, values))


if __name__ == "__main__":
    unittest.main()
