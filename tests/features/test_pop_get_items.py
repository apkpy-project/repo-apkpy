"""A name given what pop() takes or what d.get() finds keeps the item's type.

last = xs.pop() then [last] was ['9'] on the phone and [9] in CPython: the
name held the item's text. It is an item now, as k = d[k] already was (the
class B of tests/features/test_item_names.py).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from test_classes import HEAD, _cpython, _generated  # noqa: E402
from test_data_rules import TOOLING  # noqa: E402

APP = 'import json\n' + HEAD + '''

def popped():
    xs = [5, 3, 9]
    last = xs.pop()
    first = xs.pop(0)
    out.set_value(str([last, first]) + json.dumps({"x": first}) + str(xs))


def from_a_dict():
    d = {"a": 1, "b": 2.5, "t": "5"}
    v = d.pop("a")
    w = d.pop("zz", 5)
    g = d.get("b")
    h = d.get("zz", 0)
    n = d.get("none")
    t = d.get("t")
    out.set_value(str([v, w, g, h, n, t]) + str(sorted([v, h])))


def in_a_loop():
    xs = [1, 2, 3, 4]
    got = []
    for i in range(3):
        last = xs.pop()
        got.append(last)
    out.set_value(str(got) + str([last]) + str(last > 1))


def empty():
    xs = []
    try:
        v = xs.pop()
        out.set_value(str([v]))
    except IndexError as e:
        out.set_value("IndexError: " + str(e))


button("1", id="b1", command=popped, screen=home)
button("2", id="b2", command=from_a_dict, screen=home)
button("3", id="b3", command=in_a_loop, screen=home)
button("4", id="b4", command=empty, screen=home)
'''


class TheItemKeepsItsType(unittest.TestCase):

    def test_the_same_answers_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        want = _cpython(APP, [""])
        self.assertEqual(want[0], '[9, 5]{"x": 5}[3]')
        self.assertEqual(_generated(APP, [""]), want)


if __name__ == "__main__":
    unittest.main()
