# -*- coding: utf-8 -*-
"""Counter and defaultdict (features/counters.py), and lists of tuples shown
as Python shows them.

from collections import Counter stopped the build. On the phone a Counter and
a defaultdict are the dict they read like; c[k] of a Counter is c.get(k, 0),
d[k] of a defaultdict is given its default on the line before, most_common()
and str() are helpers.

The PC's org.json keeps a dict's keys in no particular order (Android's keeps
them in the order they went in), so the answers compared here never show a
dict of more than one key, or two counts that tie.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from test_classes import HEAD, _cpython, _generated
from test_python_vocabulary import _flat
from test_runtime_arithmetic import HAVE_ANDROID, helpers_compile


APP = "from collections import Counter, defaultdict\n" + HEAD + '''
WORDS = "tea jam tea cake tea jam".split()
COUNTS = Counter(WORDS)


def counting():
    t = field.get_value()
    c = Counter(WORDS + [t, t, t, t])
    c["jam"] += 10
    missing = c["nothing"]
    letters = Counter(t + "zzzzz")
    out.set_value(str(c.most_common(2)) + " " + str(missing) + " " + str(len(c))
                  + " " + str(letters.most_common(1)[0]) + " " + str(c.total())
                  + " " + str("nothing" in c) + " " + str(COUNTS["tea"]) + " " + str(COUNTS["x"])
                  + " " + str(Counter()) + " " + str(Counter([t])))


def updating():
    t = field.get_value()
    c = Counter()
    for w in ["x", "y", "x", "x", "y", "y", t]:
        c[w] += 1
    c.update(["y", "q"])
    c.subtract(["x"])
    parts = []
    for word, n in c.most_common(2):
        parts.append(word + "=" + str(n))
    top = c.most_common(1)
    out.set_value(",".join(parts) + " " + str(top) + " " + f"{Counter(['k', 'k'])}"
                  + " " + str(sorted(c)) + " " + str(c["x"]))


def grouping():
    t = field.get_value()
    groups = defaultdict(list)
    totals = defaultdict(int)
    for w in ["apple", "avocado", "banana", t]:
        groups[w[:1]].append(w)
        totals[w[:1].upper()] += len(w)
    seen = groups["zz"]
    names = defaultdict(lambda: "none")
    names["a"] = "ana"
    one = defaultdict(int)
    one["k"] += 2
    out.set_value(str(sorted(groups["a"])) + " " + str(totals["A"]) + " " + str(seen)
                  + " " + str(len(groups)) + " " + names["b"] + " " + str(len(names))
                  + " " + str(one) + " " + str("zz" in groups) + " " + str(dict(one)))


def pairs():
    n = len(field.get_value())
    d = {"b": n, "a": 1}
    out.set_value(str(sorted(d.items())) + " " + str([("x", 1), ("y", n)]) + " "
                  + str(sorted(d.items())[0]))


button("1", id="b1", command=counting, screen=home)
button("2", id="b2", command=updating, screen=home)
button("3", id="b3", command=grouping, screen=home)
button("4", id="b4", command=pairs, screen=home)
run(start_screen=home)
'''


class TheAnswersTests(unittest.TestCase):
    def test_the_same_answers_as_cpython(self):
        inputs = ["ab", "", "abcde"]
        self.assertEqual(_generated(APP, inputs), _cpython(APP, inputs))


def _refused(body, head="from collections import Counter, defaultdict\n"):
    source = head + HEAD + body + \
        '\nbutton("1", id="b1", command=go, screen=home)\nrun(start_screen=home)\n'
    files = translate_python_to_android(source)
    assert "error.txt" in files, "translated"
    return _flat(files["error.txt"])


class TheRefusalTests(unittest.TestCase):
    def test_a_read_that_may_not_run(self):
        text = _refused('def go():\n    d = defaultdict(int)\n'
                        '    ok = len(field.get_value()) > 1 and d["a"] > 0\n'
                        '    out.set_value(str(ok) + str(len(d)))\n')
        self.assertIn('Reading a missing key of a defaultdict adds it', text)

    def test_a_read_in_a_while_test(self):
        text = _refused('def go():\n    d = defaultdict(int)\n    while d["a"] < 3:\n'
                        '        d["a"] += 1\n    out.set_value(str(len(d)))\n')
        self.assertIn("a while's test runs again", text)

    def test_counters_added_together(self):
        text = _refused('def go():\n    a = Counter("ab")\n    b = Counter("bc")\n'
                        '    out.set_value(str(a + b))\n')
        self.assertIn('c.update(d) adds d to c', text)

    def test_a_counter_in_a_list(self):
        text = _refused('def go():\n    xs = [Counter("ab")]\n    out.set_value(str(len(xs)))\n')
        self.assertIn('A Counter or a defaultdict inside a list', text)

    def test_a_defaultdict_of_sets(self):
        text = _refused('def go():\n    d = defaultdict(set)\n    out.set_value(str(len(d)))\n')
        self.assertIn('defaultdict(set) keeps a set inside a dict', text)

    def test_a_lambda_factory_shown(self):
        text = _refused('def go():\n    d = defaultdict(lambda: 0)\n    out.set_value(str(d))\n')
        self.assertIn('changes on every run', text)

    def test_number_keys_shown(self):
        text = _refused('def go():\n    c = Counter([1, 2, 1])\n'
                        '    out.set_value(str(c.most_common(1)))\n')
        self.assertIn('c has numbers for keys', text)
        self.assertIn('c.most_common(1)', text)

    def test_number_keys_looked_up_are_fine(self):
        source = "from collections import Counter\n" + HEAD + (
            'def go():\n    c = Counter([1, 2, 1])\n    d = {1: "a"}\n'
            '    out.set_value(str(c[1]) + str(c[7]) + d[1] + str(1 in d))\n\n\n'
            'button("1", id="b1", command=go, screen=home)\nrun(start_screen=home)\n')
        self.assertEqual(_generated(source, ["x"]), _cpython(source, ["x"]))

    def test_a_dict_comprehension_with_number_keys_shown(self):
        text = _refused('def go():\n    n = len(field.get_value())\n'
                        '    out.set_value(str({i: i * i for i in range(n)}))\n', head="")
        self.assertIn('This dict has numbers for keys', text)

    def test_a_comprehension_of_tuples_shows_them(self):
        source = HEAD + ('def go():\n    n = len(field.get_value())\n'
                         '    out.set_value(str([(a, b) for a in range(2) for b in range(n)]))\n\n\n'
                         'button("1", id="b1", command=go, screen=home)\nrun(start_screen=home)\n')
        self.assertEqual(_generated(source, ["ab"]), _cpython(source, ["ab"]))

    def test_a_dict_with_number_keys_shown(self):
        text = _refused('def go():\n    sq = {}\n    for i in range(3):\n        sq[i] = i * i\n'
                        '    out.set_value(str(sorted(sq)))\n', head="")
        self.assertIn('sq has numbers for keys', text)


@unittest.skipUnless(HAVE_ANDROID, "no JDK or no Android SDK on this machine")
class TheHelpersCompileAgainstAndroid(unittest.TestCase):
    def test_they_compile(self):
        helpers_compile(self, APP, ("_apkpyCounterOf", "_apkpyCounterUpdate",
                                    "_apkpyCounterMostCommon", "_apkpyCounterShow",
                                    "_apkpyDefaultShow", "_apkpyShowTuples"))


if __name__ == "__main__":
    unittest.main()
