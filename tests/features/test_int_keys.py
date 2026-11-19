# -*- coding: utf-8 -*-
"""A dict whose keys are whole numbers, with its keys read back as numbers.

On the phone a dict is kept as JSON, and JSON keys are text. Until 1.15.1
str(d), for k in d, sorted(d) and the like stopped the build for a dict with
number keys (they would have given '1' where Python gives 1). When every key
the dict is ever given is a whole number, those reads are now written with
the keys turned back into numbers (apkpy_lib/core/features/int_keys.py).

The PC's org.json keeps a dict in a HashMap, so the answers compared here use
small keys put in in ascending order, where its order is the order they went
in; Android keeps that order for any keys.
"""

import re
import unittest

from apkpy_lib.core.compiler import translate_python_to_android

from test_classes import HEAD, _cpython, _generated
from test_data_rules import TOOLING

APP = HEAD + '''

COUNTS = {1: "one", 2: "two"}


def b_show():
    d = {1: "a", 2: [1, "x"], 3: {"k": 2.5}, 4: None, 5: True}
    out.set_value(str(d) + " " + repr(d) + f" {d}")


def b_count():
    counts = {}
    for n in [1, 2, 1, 3, 1]:
        counts[n] = counts.get(n, 0) + 1
    out.set_value(str(counts) + str(max(counts)) + str(sorted(counts)))


def b_loops():
    d = {1: "a", 2: "b", 10: "c"}
    total = 0
    for k in d:
        total += k
    shown = []
    for k, v in d.items():
        shown.append(str(k * 2) + v)
    out.set_value(str(total) + str(shown) + str([k + 1 for k in d.keys()]))


def b_typed():
    n = len(field.get_value())
    d = {}
    d[n] = "x"
    d[n + 1] = "y"
    out.set_value(str(d) + str(list(d)) + str(sum(d)) + str(min(d.keys())))


def b_module():
    out.set_value(str(COUNTS) + str(sorted(COUNTS)) + str(len(COUNTS)))


def b_lookups():
    d = {1: "a"}
    out.set_value(d[1] + d.get(2, "?") + str(1 in d) + str(len(field.get_value()) in d))


button("1", id="b1", command=b_show, screen=home)
button("2", id="b2", command=b_count, screen=home)
button("3", id="b3", command=b_loops, screen=home)
button("4", id="b4", command=b_typed, screen=home)
button("5", id="b5", command=b_module, screen=home)
button("6", id="b6", command=b_lookups, screen=home)
'''


def _refusal(body, top=""):
    source = HEAD + top + "\n\ndef go():\n" + body + \
        '\n\nbutton("Go", id="b1", command=go, screen=home)\n'
    return re.sub(r"\s+", " ", translate_python_to_android(source).get("error.txt", ""))


class TheAnswersTests(unittest.TestCase):

    def test_the_same_answers_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["a", "", "abc"]
        self.assertEqual(_cpython(APP, inputs), _generated(APP, inputs))


class TheRefusalsTests(unittest.TestCase):
    """A dict with a key that is not certainly a whole number keeps the refusal."""

    def test_a_float_key(self):
        self.assertIn("d has numbers for keys",
                      _refusal('    d = {1.5: "a"}\n    out.set_value(str(d))\n'))

    def test_a_bool_key(self):
        self.assertIn("d has numbers for keys",
                      _refusal('    d = {True: "a", 2: "b"}\n    out.set_value(str(d))\n'))

    def test_text_and_numbers(self):
        self.assertIn("d has numbers for keys",
                      _refusal('    d = {1: "a"}\n    d["x"] = "b"\n    out.set_value(str(d))\n'))

    def test_a_dict_filled_by_update(self):
        self.assertIn("d has numbers for keys",
                      _refusal('    d = {1: "a"}\n    d.update({})\n    out.set_value(str(d))\n'))

    def test_items_in_a_comprehension(self):
        self.assertIn("d has numbers for keys",
                      _refusal('    d = {1: "a"}\n'
                               '    out.set_value(str([k for k, v in d.items()]))\n'))

    def test_the_keys_joined(self):
        # ", ".join(d) is a TypeError in Python for number keys.
        self.assertIn("d has numbers for keys",
                      _refusal('    d = {1: "a"}\n    out.set_value(", ".join(d))\n'))

    def test_tuple_keys(self):
        text = _refusal('    d = {(1, 2): "a"}\n    out.set_value(str(d))\n')
        self.assertIn("d has tuples for keys", text)
        self.assertIn("(1, 2) as '[1,2]'", text)

    def test_a_parameter_with_the_same_name(self):
        # d in show() is whatever the caller hands it: not the module's d.
        text = _refusal('    show(D)\n', top='D = {1: "a"}\n\n\ndef show(D):\n'
                                            '    out.set_value(str(D))\n')
        self.assertIn("D has numbers for keys", text)

    def test_the_previewer_never_sees_the_rewrite(self):
        # The rewrite is of the tree the compiler reads, not of the file.
        source = HEAD + '\n\ndef go():\n    d = {1: "a"}\n    out.set_value(str(d))\n'
        translate_python_to_android(source)
        self.assertIn('out.set_value(str(d))', source)


if __name__ == "__main__":
    unittest.main()
