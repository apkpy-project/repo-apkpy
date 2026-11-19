# -*- coding: utf-8 -*-
"""Items of a list or a dict, shown and counted as CPython does (14-11-2026).

Found while the 1.15.0 compatibility page was checked against the compiler:

- `for x in xs: ys.append(x * 2)` over a list written with numbers, and
  `[x * 2 for x in xs]`, stopped the build ("could not tell that the values
  in this arithmetic are numbers") -- the very loop that message told people
  to write. The name of the for has the item as the JSON holds it, and
  _apkpyArith takes it as it takes xs[i];
- str(d["a"]) of {"a": ["tea"]}, str(xs[0]) of a list of lists, f"{row}" and
  "%s" % row showed the JSON, ["tea"] for ['tea'], without a word;
- def many(x, *_) called many(1, 2, 3) reached javac, as the unread *_ was
  dropped and the call kept its three values;
- {x: x * 2 for x in xs} over numbers was a dict with number keys that
  str() showed with '1' and no refusal.
"""

import unittest

from test_classes import HEAD, _cpython, _generated
from test_data_rules import TOOLING
from test_python_vocabulary import _error, _flat


APP = HEAD + '''
from collections import defaultdict
import json


def doubled(xs):
    return [x * 2 for x in xs]


def many(x, *_):
    return x


def tag(x, y=5, **_):
    return x + y


def loops():
    n = len(field.get_value())
    xs = [3, 1.25, n]
    ys = []
    total = 0
    for x in xs:
        ys.append(x * 2)
        total = total + x * 2
    words = ["ab", "c"]
    said = []
    for w in words:
        said.append(w * 2)
    out.set_value(str(ys) + " " + str(total) + " " + str([x * 3 for x in [n, 4]])
                  + " " + str(sorted({x // 2 for x in [n, 7, 9]})) + " " + str(doubled([n, 2]))
                  + " " + str(said) + " " + str(sum(x * 2 for x in [n, 1])))


def shown():
    n = len(field.get_value())
    d = {"a": ["tea", n], "s": "x"}
    rows = [["tea"], {"k": n}, "x", n]
    seen = ""
    for row in rows:
        seen += str(row) + f"<{row}>"
    by = defaultdict(list)
    by["a"].append("cola")
    loaded = json.loads('{"a": [1.5, null, true]}')
    out.set_value(str(d["a"]) + str(d["s"]) + " " + str(rows[0]) + str(rows[-1]) + " " + seen
                  + " " + str(by["a"]) + " " + str(loaded["a"]) + " " + str(d.get("a"))
                  + " " + f"{d['a']}" + " " + "%s|%s" % (d["a"], rows[1]))


def stars():
    n = len(field.get_value())
    out.set_value(str(many(n, 2, 3)) + str(many(n)) + " " + str(tag(n, 1, color="red"))
                  + str(tag(n)))


button("1", id="b1", command=loops, screen=home)
button("2", id="b2", command=shown, screen=home)
button("3", id="b3", command=stars, screen=home)
run(start_screen=home)
'''


class TheAnswersTests(unittest.TestCase):
    """The generated Java shows what CPython shows, button by button."""

    def test_the_same_answers_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["abc", "", "abcdefg"]
        self.assertEqual(_cpython(APP, inputs), _generated(APP, inputs))


class TheRefusalTests(unittest.TestCase):

    def test_an_unread_value_that_calls_something(self):
        text = _flat(_error('    out.set_value(str(many(1, noisy())))',
                            module_lines='def many(x, *_):\n    return x\n\n\n'
                                         'def noisy():\n    return 1\n'))
        self.assertIn('U2033', text)
        self.assertIn('many() never reads this value', text)
        self.assertIn('Work it out on the line before', text)

    def test_a_function_with_an_unread_star_handed_on(self):
        text = _flat(_error('    f = many\n    out.set_value(str(f(1, 2)))',
                            module_lines='def many(x, *_):\n    return x\n'))
        self.assertIn('many() is handed on as a value', text)

    def test_number_keys_from_a_loop_read_back(self):
        # Whole numbers, every one: read back as numbers since 1.15.1.
        self.assertIsNone(_error('    xs = [3, 1]\n    d = {}\n    for x in xs:\n        d[x] = 1\n'
                                 '    out.set_value(str(d))'))
        text = _flat(_error('    xs = [3, 1.5]\n    d = {}\n    for x in xs:\n        d[x] = 1\n'
                            '    out.set_value(str(d))'))
        self.assertIn('d has numbers for keys', text)

    def test_number_keys_from_a_comprehension_read_back(self):
        text = _flat(_error('    xs = [3, 1]\n    out.set_value(str({x: x * 2 for x in xs}))'))
        self.assertIn('has numbers for keys', text)

    def test_number_keys_from_a_list_at_the_top_looked_up(self):
        self.assertIsNone(_error('    d = {x: 0 for x in XS}\n    out.set_value(str(d[3]))',
                                 module_lines='XS = [3, 1]\n'))

    def test_text_keys_from_a_loop_are_left_alone(self):
        self.assertIsNone(_error('    xs = ["a", "b"]\n    out.set_value(str({x: 0 for x in xs}))'))


if __name__ == "__main__":
    unittest.main()
