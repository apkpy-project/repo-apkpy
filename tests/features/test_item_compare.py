# -*- coding: utf-8 -*-
"""Two values the source says nothing about, compared and copied as CPython does.

An item of a list, the name of a for over one, a parameter: none of them says
what it holds, and the phone keeps them as text. Until 1.14.2 that text was
what got compared and copied:

    best = SCORES[0]                 [x for x in SCORES]
    for s in SCORES:                 -> ['9', '12', '10']
        if s > best:
            best = s                 -> 9, the largest of [9, 12, 10]

Here the generated Java runs on the PC's JVM, button by button, next to
CPython running the same app (test_classes has the two runners). The name of a
for over a list now carries the item as the JSON holds it (_RAW_LOOP_VARS);
anything else is read as isinstance() reads it, and a text that only looked
like a number stays text against text.
"""

import unittest

from test_classes import HEAD, TOOLING, _cpython, _generated

COMPARE_APP = HEAD.replace("from apkpy_lib", "import json\nfrom apkpy_lib") + '''
SCORES = [9, 12, 10]
PRICES = [9.5, 10, 2.25]
WORDS = ["pear", "apple", "fig"]
CODES = ["10", "9", "011"]
ROWS = [{"name": "tea", "p": 9, "code": "10"}, {"name": "jam", "p": 12, "code": "9"}]
PAIRS = [[1, 2], [1, 3]]
MIXED = [1, "a", None]


class Board:
    def __init__(self):
        self.scores = []

    def add(self, n):
        self.scores.append(n)

    def best(self):
        top = self.scores[0]
        for s in self.scores:
            if s > top:
                top = s
        return top


def largest(items):
    top = items[0]
    for x in items:
        if x > top:
            top = x
    return top


def bigger(a, b):
    if a > b:
        return a
    return b


def compare():
    lines = [str(largest(SCORES)), str(largest(PRICES)), largest(WORDS), largest(CODES)]
    top = ROWS[0]
    for r in ROWS:
        if r["p"] > top["p"]:
            top = r
    lines.append(top["name"])
    lines.append(str(ROWS[0]["code"] > ROWS[1]["code"]))
    lines.append(str(PAIRS[0] < PAIRS[1]))
    lines.append(str(SCORES[0] <= SCORES[0]) + " " + str(SCORES[1] >= SCORES[2]))
    lines.append(str(PRICES[0] < SCORES[2]))
    lines.append(str(SCORES[0] < SCORES[2] < SCORES[1]))
    lines.append(str([x for x in SCORES if x > SCORES[0]]))
    lines.append(str(bigger(9, 12)) + " " + bigger("pear", "fig"))
    board = Board()
    board.add(len(field.get_value()) + 3)
    board.add(len(field.get_value()) + 11)
    board.add(len(field.get_value()) + 7)
    lines.append(str(board.best()))
    i = 0
    while SCORES[i] < SCORES[1]:
        i += 1
    lines.append(str(i))
    lines.append(str(field.get_value() < "9"))
    try:
        lines.append(str(MIXED[0] < MIXED[1]))
    except TypeError as e:
        lines.append("TypeError: " + str(e))
    try:
        lines.append(str(MIXED[2] > MIXED[0]))
    except TypeError as e:
        lines.append("TypeError: " + str(e))
    out.set_value(" | ".join(lines))


def copies():
    a = [x for x in SCORES]
    b = []
    for x in SCORES:
        b.append(x)
    d = [s for s in SCORES if s != 12]
    e = [c for c in CODES]
    f = [r for r in ROWS]
    grid = [[1], [2]]
    grown = []
    for row in grid:
        row.append(0)
        grown.append(row)
    lines = [str(a), str(b), str(d), str(sum(a)), str(e), str(len(f)) + " " + f[1]["name"],
             str(grown), json.dumps([x for x in PRICES]), str(sorted(b)),
             json.dumps([c for c in CODES])]
    out.set_value(" | ".join(lines))


button("1", id="b1", command=compare, screen=home)
button("2", id="b2", command=copies, screen=home)
'''


class TheItemCompareTests(unittest.TestCase):
    """The generated Java compares and copies what CPython compares and copies."""

    def test_the_same_answers_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["", "10"]
        self.assertEqual(_cpython(COMPARE_APP, inputs), _generated(COMPARE_APP, inputs))


if __name__ == "__main__":
    unittest.main()
