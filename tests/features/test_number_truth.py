# -*- coding: utf-8 -*-
"""A number as a condition: `if i % 2:`, `while n // 10:`, `x if n - 5 else y`.

Python counts 0 and 0.0 as false and every other number as true. Until 1.15.1
an if, a while, a comprehension's if or a conditional expression whose test
was arithmetic was refused (or, at the top of the file, dropped). It is
written now as the truth of the number the arithmetic gives, the same
_apkpyTruthy the rest of the conditions use.

Also held here: a name the top of the file sets inside if, for or while, and
that a function reads, and `x = storage.get("k") + "!"` at the top of the
file. Both left Java that javac refused, or a value nobody set; both are
refused now, with the line, before any Java is written.
"""

import re
import unittest

from apkpy_lib.core.compiler import translate_python_to_android

from test_classes import HEAD, _cpython, _generated
from test_data_rules import TOOLING

APP = HEAD + '''

def odd(k):
    if k % 2:
        return "odd"
    return "even"


def b_if():
    n = int(field.get_value() or "5")
    found = []
    for i in range(n):
        if i % 2:
            found.append(i)
    out.set_value(str(found))


def b_ifexp():
    n = int(field.get_value() or "5")
    out.set_value("not five" if n - 5 else "five")


def b_comp():
    n = int(field.get_value() or "5")
    out.set_value(str([i for i in range(n) if i % 2]) + str([i for i in range(n) if not i % 3]))


def b_while():
    n = int(field.get_value() or "5") * 1000 + 7
    digits = 0
    while n // 10:
        n = n // 10
        digits += 1
    out.set_value(str(digits))


def b_items():
    rows = [{"n": 3}, {"n": 4}, {"n": 0}]
    r = ""
    for row in rows:
        if row["n"] % 2:
            r += "odd "
        else:
            r += "even "
    out.set_value(r)


def b_floats():
    xs = [3, 4, 2.5, 0]
    r = []
    for x in xs:
        if x * 2 - 5:
            r.append(x)
    out.set_value(str(r))


def b_mixed():
    n = len(field.get_value())
    a = "y" if n % 2 and n > 1 else "n"
    b = "yes" if -n else "no"
    c = "some" if field.get_value() + "" else "none"
    out.set_value(a + b + c + odd(n) + odd(4))


button("1", id="b1", command=b_if, screen=home)
button("2", id="b2", command=b_ifexp, screen=home)
button("3", id="b3", command=b_comp, screen=home)
button("4", id="b4", command=b_while, screen=home)
button("5", id="b5", command=b_items, screen=home)
button("6", id="b6", command=b_floats, screen=home)
button("7", id="b7", command=b_mixed, screen=home)
'''


def _error(source):
    files = translate_python_to_android(source)
    return re.sub(r"\s+", " ", files.get("error.txt", ""))


class TheAnswersTests(unittest.TestCase):

    def test_the_same_answers_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["7", "", "12", "0"]
        self.assertEqual(_cpython(APP, inputs), _generated(APP, inputs))


class TheJavaTests(unittest.TestCase):

    def test_an_if_on_arithmetic_is_its_truth(self):
        files = translate_python_to_android(APP)
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:600])
        java = files["java/Screen_homeActivity.java"]
        self.assertIn("_apkpyTruthy(_apkpyArithValue(", java)

    def test_at_the_top_of_the_file(self):
        # Only the top of the file reads what the if decides: that is
        # translated, in onCreate.
        source = HEAD + '''
N = 7
if N % 2:
    out.set_value("odd")
else:
    out.set_value("even")


def go():
    pass


button("Go", id="b1", command=go, screen=home)
'''
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:600])
        java = files["java/Screen_homeActivity.java"]
        on_create = java[java.index("protected void onCreate"):]
        # N is a whole number known here: its truth is written as != 0.
        self.assertRegex(on_create[:on_create.index('"even"')],
                         r"if \(.*(_apkpyTruthy\(|\) != 0\)).*\n.*\"odd\"")


class TheTopOfTheFileTests(unittest.TestCase):

    def _top(self, top, body='    out.set_value(str(res))\n'):
        return (HEAD.replace("import Screen", "import storage, Screen") + top
                + '\n\ndef go():\n' + body
                + '\n\nbutton("Go", id="b1", command=go, screen=home)\n')

    def test_a_name_an_if_sets_and_a_function_reads(self):
        text = _error(self._top('N = 7\nres = ""\nif N % 2:\n    res = "odd"\nelse:\n'
                                '    res = "even"\n'))
        self.assertIn("U2033", text)
        self.assertIn("res = ... inside an if", text)
        self.assertIn("Move the if into the function that reads res", text)

    def test_a_name_a_for_loop_sets_and_a_function_reads(self):
        text = _error(self._top('res = 0\nfor x in [1, 2, 3]:\n    res += x\n'))
        self.assertIn("res = ... inside a for loop", text)

    def test_a_function_with_its_own_name_is_not_refused(self):
        source = self._top('res = 0\nfor x in [1, 2, 3]:\n    res += x\n',
                           body='    res = "mine"\n    out.set_value(res)\n')
        files = translate_python_to_android(source)
        self.assertNotIn("res = ... inside", files.get("error.txt", ""))

    def test_a_saved_value_inside_an_expression(self):
        for line in ('res = int(storage.get("n", 0))',
                     'res = storage.get("k") + "!"',
                     'res = storage.get("k") or "none"',
                     'res = "a" if storage.get("k") else "b"'):
            text = _error(self._top(line))
            self.assertIn("a saved value is read on a line of its own", text, line)

    def test_a_saved_value_on_its_own_line_still_works(self):
        files = translate_python_to_android(self._top('res = storage.get("k", "a")\n'))
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:600])
        self.assertIn('String res = _apkpyStorageGet("k", "a");',
                      files["java/Screen_homeActivity.java"])


if __name__ == "__main__":
    unittest.main()
