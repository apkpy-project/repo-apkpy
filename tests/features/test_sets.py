# -*- coding: utf-8 -*-
"""set: a list without repeats, in the order CPython walks it (features/sets.py).

set(), {1, 2} and set comprehensions stopped the build. On the phone a set is
kept as the JSON list of its items, so a for, `in`, len() and sorted() read it
as they read a list; add, discard, | & - ^, <= and str() are helpers that keep
the items unique and in CPython's order: {3, 1, 2} shows {1, 2, 3}, and
{16, 1, 2, 3, 4} shows {16, 1, 2, 3, 4}, as CPython makes a literal of
constants another way.
"""

import random
import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features.sets import cpython_order
from test_classes import HEAD, _cpython, _generated
from test_python_vocabulary import _flat
from test_runtime_arithmetic import HAVE_ANDROID, helpers_compile


APP = HEAD + '''
SEEN = set()
NAMES = ["b", "a", "b"]
FIRST = set(NAMES)
TAGS = {16, 1, 2, 3, 4}


class Basket:
    def __init__(self):
        self.ids = set()

    def put(self, i):
        self.ids.add(i)
        return len(self.ids)


def common(a, b):
    return a & b


def remember(x):
    SEEN.add(x)


def made(n):
    return {n, 1}


def building():
    n = len(field.get_value())
    a = {3, 1, 2}
    b = set([n, 5, n])
    c = {x * x for x in range(-3, 4) if x != n}
    d = {-1, -2, 8, 0, 64, 32}
    e = {16, 1, 2, 3, n}
    out.set_value(str(a) + " " + str(b) + " " + str(c) + " " + str(d) + " " + str(e)
                  + " " + str(set()) + " " + str(TAGS) + " " + f"{made(n)}"
                  + " " + str(sorted(set("hello"))) + " " + str(len({1, 1.0, True})))


def operators():
    n = len(field.get_value())
    a = {2, 3, 5, 7}
    b = {3, 4, 5, n}
    out.set_value(str(a | b) + " " + str(a & b) + " " + str(a - b) + " " + str(a ^ b)
                  + " " + str(a.union([8], (9,))) + " " + str(a.intersection(b))
                  + " " + str({1, 2} <= {1, 2, n}) + str({1, 2} < {1, 2}) + str(a == {7, 5, 3, 2})
                  + str(a != b) + str(a.isdisjoint({n})) + str({1, 2, 3}.issuperset([1, n])))


def changing():
    n = len(field.get_value())
    s = {1}
    s.add(n)
    s.add(n)
    s.update([2, 3], {n + 10})
    s.discard(99)
    s.difference_update({1})
    s -= {3}
    gone = str(s)
    s |= {40}
    fresh = {9, n, 4}
    first = fresh.pop()
    t = s.copy()
    t.add(1000)
    try:
        s.remove(n + 500)
        msg = "ok"
    except KeyError as e:
        msg = "K" + str(e)
    try:
        empty = set()
        empty.pop()
    except KeyError as e:
        msg += "|" + str(e)
    # After items went out and others came in, CPython's table keeps the gaps
    # and its size: the order can differ there (sets.py), sorted() is the same.
    out.set_value(gone + " " + str(sorted(s)) + " " + str(first) + str(fresh) + " "
                  + str(sorted(t)) + " " + msg)


def reading():
    n = len(field.get_value())
    s = {7, n, 3, 10}
    parts = []
    for i, v in enumerate(s):
        parts.append(str(i) + ":" + str(v))
    w = set("hello world".split())
    k = set({"x": 1, "y": 2})
    msg = "yes" if s else "no"
    if not set():
        msg += "!"
    out.set_value(",".join(parts) + " " + str(max(s)) + " " + str(sum(s)) + " " + str(min(s))
                  + " " + str(sorted(s, reverse=True)) + " " + str(sorted(w)) + " " + str(sorted(k))
                  + " " + str(list({5, n})) + " " + str(n in s) + " " + msg
                  + " " + str({1.5, 2.25, 0.1, -3.75, 1e20}))


def shared():
    n = len(field.get_value())
    remember(n)
    remember(n)
    remember(42)
    basket = Basket()
    basket.put(n)
    k = basket.put(5)
    copy = set(FIRST)
    copy.add("c")
    both = common({1, 2, n}, {2, n, 9})
    seen = set()
    seen.add((1, 2))
    seen.add((1, n))
    out.set_value(str(sorted(SEEN)) + " " + str(len(SEEN)) + " " + str(k) + " " + str(sorted(FIRST))
                  + " " + str(sorted(copy)) + " " + str(both) + " " + str(len(seen))
                  + str((1, 2) in seen) + " " + str(set(field.get_value()) == set("ba")))


button("1", id="b1", command=building, screen=home)
button("2", id="b2", command=operators, screen=home)
button("3", id="b3", command=changing, screen=home)
button("4", id="b4", command=reading, screen=home)
button("5", id="b5", command=shared, screen=home)
run(start_screen=home)
'''


class TheAnswersTests(unittest.TestCase):
    def test_the_same_answers_as_cpython(self):
        inputs = ["ab", "", "abcde"]
        self.assertEqual(_generated(APP, inputs), _cpython(APP, inputs))


class TheOrderTests(unittest.TestCase):
    """The order CPython walks a set of numbers in, worked out here."""

    def test_built_one_by_one_and_written_as_constants(self):
        rng = random.Random(5)
        for _ in range(800):
            pool = rng.choice([range(-50, 200), range(0, 2000),
                               [x * 0.5 for x in range(-40, 80)]])
            items = [rng.choice(list(pool)) for _ in range(rng.randint(3, 40))]
            unique = []
            for item in items:
                if not any(item == u for u in unique):
                    unique.append(item)
            literal = eval(compile("{%s}" % ", ".join(repr(i) for i in items), "x", "eval"))
            self.assertEqual([repr(v) for v in cpython_order(unique, literal=True)],
                             [repr(v) for v in literal])
            self.assertEqual([repr(v) for v in cpython_order(unique)],
                             [repr(v) for v in set(items)])

    def test_text_keeps_the_order_it_went_in(self):
        self.assertEqual(cpython_order(["pear", "fig", 3]), ["pear", "fig", 3])


def _refused(body):
    source = HEAD + body + '\nbutton("1", id="b1", command=go, screen=home)\nrun(start_screen=home)\n'
    files = translate_python_to_android(source)
    assert "error.txt" in files, "translated"
    return _flat(files["error.txt"])


class TheRefusalTests(unittest.TestCase):
    """What would show or behave another way on the phone stops the build."""

    def test_a_set_inside_a_list(self):
        text = _refused('def go():\n    groups = [{1}, {2}]\n    out.set_value(str(groups))\n')
        self.assertIn('A set inside a list, a tuple or a dict', text)

    def test_a_set_put_in_a_dict(self):
        text = _refused('def go():\n    d = {}\n    d["a"] = {1}\n    out.set_value(str(d))\n')
        self.assertIn('A set inside a list, a tuple or a dict', text)

    def test_a_set_appended(self):
        text = _refused('def go():\n    xs = []\n    xs.append({1})\n    out.set_value(str(xs))\n')
        self.assertIn('A set inside a list, a tuple or a dict', text)

    def test_a_set_compared_with_a_list(self):
        text = _refused('def go():\n    out.set_value(str({1, 2} == [1, 2]))\n')
        self.assertIn('{1, 2} == [1, 2] is False', text)

    def test_json_of_a_set(self):
        text = _refused('import json\n\n\ndef go():\n    out.set_value(json.dumps({1}))\n')
        self.assertIn('not JSON serializable', text)

    def test_frozenset(self):
        text = _refused('def go():\n    out.set_value(str(frozenset([1])))\n')
        self.assertIn('frozenset is not translated yet', text)

    def test_changing_a_set_at_the_top_of_the_file(self):
        text = _refused('TAGS = set()\nTAGS.add(1)\n\n\ndef go():\n    out.set_value(str(TAGS))\n')
        self.assertIn('Changing a set at the top of the file', text)

    def test_a_function_that_changes_the_set_it_is_given(self):
        text = _refused('def put(s, x):\n    s.add(x)\n\n\ndef go():\n    tags = {1}\n'
                        '    put(tags, 2)\n    out.set_value(str(tags))\n')
        self.assertIn('put() changes s', text)

    def test_two_names_for_one_set(self):
        text = _refused('def go():\n    a = {1}\n    b = a\n    b.add(2)\n    out.set_value(str(a))\n')
        self.assertIn('another name for the same object', text)


@unittest.skipUnless(HAVE_ANDROID, "no JDK or no Android SDK on this machine")
class TheHelpersCompileAgainstAndroid(unittest.TestCase):
    def test_they_compile(self):
        helpers_compile(self, APP, (
            "_apkpySetOf", "_apkpySetAdd", "_apkpySetRemove", "_apkpySetUnion", "_apkpySetInter",
            "_apkpySetDiff", "_apkpySetSymDiff", "_apkpySetCompare", "_apkpySetShow",
            "_apkpySetPopValue", "_apkpySetRest"))


if __name__ == "__main__":
    unittest.main()
