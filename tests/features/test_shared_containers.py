# -*- coding: utf-8 -*-
"""One list under two names, what a function answers, and lists of numbers.

On the phone a list or a dict is a value, the JSON text of one. Until 1.14.2
these built and ran, and showed what CPython would not:

    l2 = l1; l2.reverse()            l1 reversed in CPython, not on the phone
    def add(x, tags=[])              one list for every call in CPython
    def add(cart, x): cart.append(x) add(CART, "tea") left CART empty
    str(evens(xs))                   "[2,4]", the JSON, for [2, 4]
    "te" in names()                  True: it searched the JSON's letters
    for x in [4, 9]: ys.append(x)    ['4', '9']

The first three stop the build now (features/shared_containers.py), with the
way to write them that answers the same on both; what is only read, or
copied on purpose, still builds. The others answer what CPython answers, on
the PC's JVM, next to CPython running the same app (test_classes' runners).
Also here: `if tags is None: tags = []`, which javac stopped on, because the
parameter was declared a second time.
"""

import ast
import unittest
from unittest.mock import patch

from apkpy_lib.core.compiler import translate_python_to_android
from test_classes import HEAD, TOOLING, _cpython, _generated


def _app(top, body):
    return (HEAD.replace("from apkpy_lib", "import json\nfrom apkpy_lib") + top + "\n\n"
            "def go():\n" + "".join("    " + line + "\n" for line in body.strip("\n").split("\n"))
            + "\n\nbutton('Go', id='b1', command=go, screen=home)\n")


def _error(top, body):
    return translate_python_to_android(_app(top, body)).get("error.txt")


class TheRefusalTests(unittest.TestCase):
    """Where CPython shares one object the phone would copy, the build stops."""

    def _refused(self, top, body, *words):
        text = _error(top, body)
        self.assertIsNotNone(text, "built, and would have answered differently")
        self.assertIn("U2033", text)
        text = " ".join(text.split())        # the message is wrapped at 76 columns
        for word in words:
            self.assertIn(word, text)
        self.assertNotIn("_apkpy_", text)
        return text

    def _builds(self, top, body):
        self.assertIsNone(_error(top, body))

    def test_a_list_default_that_the_function_changes(self):
        text = self._refused("def add(x, tags=[]):\n    tags.append(x)\n    return tags\n",
                             "out.set_value(str(add('a')))",
                             "tags=[] is made once", "if tags is None: tags = []")
        self.assertIn("def add(..., tags=[])", text)
        self._refused("def note(k, seen={}):\n    seen[k] = 1\n    return len(seen)\n",
                      "out.set_value(str(note('a')))", "seen={}")
        self._refused("class Box:\n    def __init__(self, tags=[]):\n        self.tags = tags\n",
                      "b = Box()\nout.set_value(str(b.tags))", "tags=[]")

    def test_a_list_default_that_is_only_read_builds(self):
        self._builds("def count(x, tags=[]):\n    n = 0\n    for t in tags:\n        n += 1\n"
                     "    return n + len(tags) + len(x)\n",
                     "out.set_value(str(count('ab')))")

    def test_a_second_name_that_is_changed(self):
        self._refused("", "l1 = [3, 1, 2]\nl2 = l1\nl2.reverse()\nout.set_value(str(l1))",
                      "l2 = l1 (line", "list(l1)")
        self._refused("", "rows = [{'n': 'tea'}]\nrow = rows[0]\nrow['n'] = 'jam'\n"
                      "out.set_value(json.dumps(rows))",
                      "row = rows[0] (line", "rows[0].copy()")
        self._refused("", "d = {'tags': ['a']}\ntags = d.get('tags')\ntags.append('c')\n"
                      "out.set_value(json.dumps(d))", "tags = d.get('tags')")
        self._refused("NUMS = [9, 12]\n", "l1 = NUMS\nl1.append(1)\nout.set_value(str(NUMS))",
                      "l1 = NUMS (line")

    def test_the_first_name_changed_while_the_second_is_read(self):
        self._refused("", "l1 = [3, 1, 2]\nl2 = l1\nl1.append(9)\nout.set_value(str(l2))",
                      "l2 = l1 (line", "l2 sees this change")

    def test_a_second_name_that_nobody_reads_again_builds(self):
        # CPython changes rows too, and nothing ever looks at rows again.
        self._builds("", "rows = [{'n': 'tea'}]\nrow = rows[0]\nrow['n'] = 'jam'\n"
                     "out.set_value(row['n'])")

    def test_appending_to_the_variable_of_a_for(self):
        self._refused("", "grid = [[1, 2], [3]]\nfor row in grid:\n    row.append(0)\n"
                      "out.set_value(str(grid))", "variable of a for loop", "range(len(grid))")

    def test_a_function_that_changes_the_list_it_is_given(self):
        text = self._refused("CART = []\n\ndef add(cart, x):\n    cart.append(x)\n",
                             "add(CART, 'tea')\nout.set_value(str(CART))",
                             "add() changes cart", "return cart", "global CART")
        self.assertIn("CART = add(CART, 'tea')", text)
        self._refused("def add(cart, x):\n    cart.append(x)\n    return cart\n",
                      "c = []\nadd(c, 'tea')\nout.set_value(str(c))", "Take the answer back")

    def test_taking_the_answer_back_builds(self):
        self._builds("def add(cart, x):\n    cart.append(x)\n    return cart\n",
                     "c = []\nc = add(c, 'tea')\nout.set_value(str(c))")
        self._builds("def add(cart, x):\n    cart.append(x)\n    return cart\n",
                     "out.set_value(str(add(['a'], 'b')))")

    def test_copies_made_on_purpose_build(self):
        self._builds("", "l1 = [3, 1]\nl2 = list(l1)\nl2.reverse()\n"
                     "rows = [{'n': 'tea'}]\nrow = rows[0].copy()\nrow['n'] = 'jam'\n"
                     "out.set_value(str(l1) + json.dumps(rows))")

    def test_a_comprehension_refused_shows_its_own_names(self):
        text = _error("", "t = field.get_value()\nout.set_value(str([x * 2 for x in t]))")
        self.assertIsNotNone(text)
        self.assertNotIn("_apkpy_c", text)
        if hasattr(ast, "unparse"):          # 3.8 quotes only the kind of node
            self.assertIn("x * 2", text)

    def test_the_messages_quote_the_code_on_python_38(self):
        # No ast.unparse() on 3.8: describe() would say "Subscript" for rows[0].
        with patch.object(ast, "unparse", None, create=True):
            text = _error("", "rows = [{'n': 'tea'}]\nrow = rows[0]\nrow['n'] = 'jam'\n"
                          "out.set_value(json.dumps(rows))")
            default = _error("def add(x, tags=['a']):\n    tags.append(x)\n    return tags\n",
                             "out.set_value(str(add('b')))")
        text, default = " ".join(text.split()), " ".join(default.split())
        self.assertIn("row = rows[0] (line", text)
        self.assertIn("row['n'] = 'jam'", text)
        self.assertIn("rows[0].copy()", text)
        self.assertIn("tags=['a']", default)


SHARED_APP = HEAD.replace("from apkpy_lib", "import json\nfrom apkpy_lib") + '''
NUMS = [9, 12, 10, -3, 0]
FLOATS = [9.5, 10.25, 2.5]
MIXED = [1, 2.5]


def add(x, tags=None):
    if tags is None:
        tags = []
    tags.append(x)
    return tags


def put(cart, x):
    cart.append(x)
    return cart


def evens(xs):
    found = []
    for x in xs:
        if int(x) % 2 == 0:
            found.append(x)
    return found


def names():
    return ["tea", "jam"]


def prices():
    return {"tea": 2, "jam": 3}


def count(x, tags=[]):
    return len(tags) + len(x)


def answers():
    t = field.get_value()
    add("a")
    lines = [str(add("b")), str(add("c", ["z"])), str(count(t))]
    c = []
    c = put(c, "tea")
    c = put(c, t)
    lines += [str(c), str(len(c)), str(evens([1, 2, 3, 4])), str(names()), str(prices())]
    lines += [str("tea" in names()), str("te" in names()), str("jam" in prices())]
    e = evens(NUMS)
    lines += [str(e), str(len(e)), str(max(evens([1, 2, 3, 4]))), str(sorted(names()))]
    out.set_value(" | ".join(lines))


def numbers():
    t = field.get_value()
    n = len(t)
    ys = []
    for y in [4, -9, 7]:
        if y < 5:
            ys.append(y)
    fs = []
    for z in [1.5, -2.5]:
        fs.append(z)
    ms = []
    for m in [1, 2.5]:
        ms.append(m)
    best = NUMS[0]
    for x in NUMS:
        if x > best:
            best = x
    lines = [str(ys), str(fs), str(ms), str([x for x in [-4, 9, -5] if x < 1])]
    kept = []
    kept.append(best)
    kept.append([4, 15, 7][0])
    lines += [str(kept), str(NUMS[1] * 2), str(FLOATS[0] + 1), str(max(NUMS) - 1),
              str(min(FLOATS) * 2), str(sum(NUMS) - 1.5), str(sum(MIXED))]
    lines += [str(NUMS + [max(NUMS)]), json.dumps(sum(FLOATS)), str(sum(FLOATS) + n),
              json.dumps([n if n > 2 else "short", -abs(n), sum(NUMS)]),
              json.dumps({"total": sum(FLOATS) + 1, "n": n % 3}, sort_keys=True)]
    xs = list(NUMS)
    xs.append(sum(xs))
    xs.insert(0, round(sum(FLOATS)))
    lines.append(str(xs))
    a = sum([n, 3])
    b = sum([4, n])
    sums = []
    sums.append(a)
    sums.append(max(n, NUMS[0] if t else 1))
    lines += [str(a + b), str(sums), str(min(min(NUMS), (n if t else 0)) + n)]
    out.set_value(" | ".join(lines))


def allowed():
    t = field.get_value()
    rows = [{"n": "tea", "done": False}]
    row = rows[0]
    first_name = row["n"]
    l1 = [3, 1, 2]
    l2 = list(l1)
    l2.reverse()
    copy = rows[0].copy()
    copy["done"] = True
    grid = [[1, 2], [3]]
    for i in range(len(grid)):
        grid[i].append(0)
    grown = []
    for g in [[1], [2]]:
        g.append(t)
        grown.append(g)
    lines = [first_name, str(l1), str(l2), json.dumps(copy["done"]), str(grid), str(grown)]
    out.set_value(" | ".join(lines))


button("1", id="b1", command=answers, screen=home)
button("2", id="b2", command=numbers, screen=home)
button("3", id="b3", command=allowed, screen=home)
'''


class TheSameAnswersTests(unittest.TestCase):
    """What builds answers what CPython answers."""

    def test_the_same_answers_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["", "10"]
        self.assertEqual(_cpython(SHARED_APP, inputs), _generated(SHARED_APP, inputs))


if __name__ == "__main__":
    unittest.main()
