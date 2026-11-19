# -*- coding: utf-8 -*-
"""The top of the file worked out at build (features/module_constants.py), and
names Java cannot take renamed (features/java_names.py).

SQUARES = [i * i for i in range(5)] at the top of the file stopped the build,
and R = 6371 or a parameter called new made javac stop on a line the
generator wrote. Both now give CPython's answers.
"""

import ast
import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import java_names, module_constants
from test_classes import HEAD, _cpython, _generated
from test_python_vocabulary import _flat


APP = "import math\n" + HEAD + '''
NAMES = sorted(["rui", "ana", "eva"])
N = len(NAMES)
SQUARES = [i * i for i in range(5)]
TOTAL = sum(SQUARES)
WORDS = "red green blue".split()
JOINED = "-".join(w.upper() for w in WORDS)
PLACE = {name: i for i, name in enumerate(NAMES)}
ROOT = math.sqrt(16) + math.pi * 0
BIG = 2 ** 40
EVEN = [x for x in range(10) if x % 2 == 0]
FIRST = NAMES[0].title()
PAIRS = list(zip(NAMES, SQUARES))
SEEN = set(WORDS)
ODDS = {1, 3, 5, 16, 2}
COUNT = 0
R = 6371
View = "panel"
org = "acme"
final = 3


def area(new, default=2):
    return new * default


def bump():
    global COUNT
    COUNT += 1
    return COUNT


def constants():
    n = len(field.get_value())
    out.set_value(str(NAMES) + " " + str(N) + " " + str(SQUARES) + " " + str(TOTAL + n)
                  + " " + str(WORDS) + " " + JOINED + " " + str(PLACE["eva"]) + str(sorted(PLACE)) + " " + str(ROOT)
                  + " " + str(BIG) + " " + str(EVEN) + " " + FIRST + " " + str(PAIRS[1])
                  + " " + str(sorted(SEEN)) + " " + str(ODDS))


def names():
    n = len(field.get_value())
    case = n + 1
    switch = "on" if n else "off"
    out.set_value(str(R + n) + " " + View + " " + org + " " + str(final * case) + " " + switch
                  + " " + str(area(n)) + " " + str(area(new=3, default=n)) + " " + str(bump())
                  + " " + str(bump()))


button("1", id="b1", command=constants, screen=home)
button("2", id="b2", command=names, screen=home)
run(start_screen=home)
'''


class TheAnswersTests(unittest.TestCase):
    def test_the_same_answers_as_cpython(self):
        inputs = ["ab", "", "abcde"]
        self.assertEqual(_generated(APP, inputs), _cpython(APP, inputs))


def _fold(source):
    return ast.unparse(module_constants.fold(ast.parse(source)))


@unittest.skipUnless(hasattr(ast, "unparse"),
                     "ast.unparse() is 3.9+: these read the rewritten source back as text")
class TheFoldTests(unittest.TestCase):
    def test_a_value_worked_out_from_names_above_it(self):
        text = _fold("A = [1, 2]\nB = sum(A) * 10\n")
        self.assertIn("B = 30", text)

    def test_a_name_changed_in_place_is_not_read_later(self):
        text = _fold("A = [1, 2]\nA.append(3)\nB = len(A)\n")
        self.assertIn("B = len(A)", text)

    def test_a_name_a_function_changes_is_not_read_later(self):
        text = _fold("A = 1\nB = A + 1\n\n\ndef f():\n    global A\n    A = 5\n")
        self.assertIn("B = A + 1", text)

    def test_two_names_for_one_list_are_left_alone(self):
        text = _fold("A = [1, 2]\nB = A\n")
        self.assertIn("B = A", text)

    def test_what_reads_the_phone_is_left_alone(self):
        text = _fold("A = storage.get('k')\nB = len(A)\n")
        self.assertIn("B = len(A)", text)

    def test_a_huge_range_is_left_alone(self):
        text = _fold("A = list(range(10 ** 9))\n")
        self.assertIn("range(10 ** 9)", text)


def _renamed(source):
    return ast.unparse(java_names.rename(ast.parse(source)))


@unittest.skipUnless(hasattr(ast, "unparse"),
                     "ast.unparse() is 3.9+: these read the rewritten source back as text")
class TheRenameTests(unittest.TestCase):
    def test_a_java_keyword_and_its_keyword_argument(self):
        text = _renamed("def f(new):\n    return new\n\n\nf(new=1)\n")
        self.assertIn("def f(new_):", text)
        self.assertIn("f(new_=1)", text)

    def test_names_the_generated_java_uses(self):
        text = _renamed("R = 1\norg = 2\nprint(R + org)\n")
        self.assertIn("R_ = 1", text)
        self.assertIn("org_ = 2", text)

    def test_what_keeps_its_name(self):
        text = _renamed("import math\nstorage.get('k', default='')\n\n\nclass View:\n    pass\n")
        self.assertIn("default=''", text)
        self.assertIn("class View", text)

    def test_a_taken_name_gets_another_underscore(self):
        text = _renamed("new = 1\nnew_ = 2\nprint(new + new_)\n")
        self.assertIn("new__ = 1", text)


class TheRefusalTests(unittest.TestCase):
    def test_a_parameter_given_a_number_and_text_and_put_in_a_list(self):
        source = HEAD + ('def made(n):\n    return [n]\n\n\ndef go():\n'
                         '    out.set_value(str(made(len(field.get_value()))) + str(made("t")))\n\n\n'
                         'button("1", id="b1", command=go, screen=home)\nrun(start_screen=home)\n')
        files = translate_python_to_android(source)
        self.assertIn("error.txt", files)
        self.assertIn("is given a number as n", _flat(files["error.txt"]))


if __name__ == "__main__":
    unittest.main()
