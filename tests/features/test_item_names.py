# -*- coding: utf-8 -*-
"""A name given an item, used as CPython uses it.

    data = json.loads(text)
    k = data["n"]
    shown = json.dumps({"k": k})      -> {"k": 5}, not {"k": "5"}

The source does not say what `k` holds, and the phone keeps a name like it as
text. Until 1.14.2 that text is what went into dumps, lists, comparisons and
isinstance(): a number read out of JSON came back quoted. Now a name given an
item once carries the item as the JSON holds it, and a name given an item more
than once (in a loop, in two branches) is kept up to date at each assignment.

Here the generated Java runs on the PC's JVM, button by button, next to
CPython running the same app (test_classes has the two runners).
"""

import unittest

from test_classes import HEAD, TOOLING, _cpython, _generated

CASES = [
    # one item, read once
    '''data = json.loads('{"n": 5}')
    k = data["n"]
    shown = json.dumps({"k": k})''',
    '''data = json.loads('{"n": "5"}')
    k = data["n"]
    shown = json.dumps({"k": k})''',
    '''rows = json.loads('[10, 9, 12]')
    first = rows[0]
    xs = [first, 1]
    shown = str(xs) + " " + str(sorted([first, 3]))''',
    '''data = json.loads('{"price": 2.5}')
    p = data["price"]
    xs = []
    xs.append(p)
    shown = str(xs)''',
    '''a = json.loads('{"n": 7, "s": "7"}')
    n = a["n"]
    s = a["s"]
    b = {}
    b["n"] = n
    b["s"] = s
    shown = json.dumps(b, sort_keys=True)''',
    '''data = json.loads('{"n": 12}')
    k = data["n"]
    shown = str(k > 9) + " " + str(k == 12)''',
    '''data = json.loads('{"n": 12, "s": "x"}')
    k = data["n"]
    t = data["s"]
    shown = str(isinstance(k, int)) + str(isinstance(t, str))''',
    '''data = json.loads('{"n": 5, "name": "Ana"}')
    k = data["n"]
    who = data["name"]
    shown = "n=" + str(k) + " " + who + " " + str(k + 1)''',
    '''data = json.loads('{"user": {"id": 3, "tags": ["a"]}}')
    u = data["user"]
    shown = json.dumps({"u": u}, sort_keys=True)''',
    # what is typed decides the number
    '''data = json.loads('{"n": ' + str(len(field.get_value())) + '}')
    k = data["n"]
    shown = json.dumps([k, k])''',
    # given an item more than once
    '''data = json.loads('{"n": 5, "m": 6}')
    k = data["n"]
    k = data["m"]
    shown = json.dumps({"k": k})''',
    '''data = json.loads('{"n": 5}')
    if len(data) > 0:
        k = data["n"]
    else:
        k = 0
    shown = json.dumps({"k": k})''',
    '''rows = json.loads('[{"price": 10}, {"price": 9}, {"price": 2.5}]')
    prices = []
    for row in rows:
        price = row["price"]
        prices.append(price)
    shown = str(sorted(prices)) + " " + json.dumps(prices)''',
    '''data = json.loads('{"n": 5}')
    if "n" in data:
        k = data["n"]
        inside = json.dumps([k])
    shown = inside + " " + json.dumps([k])''',
    '''rows = json.loads('[4, 11, 7]')
    i = 0
    best = []
    while i < len(rows):
        x = rows[i]
        if x > 5:
            best.append(x)
        i += 1
    shown = str(best)''',
    '''data = json.loads('{"n": 5}')
    try:
        k = data["n"]
        shown = json.dumps({"k": k})
    except KeyError:
        shown = "missing"''',
]

ITEMS_APP = HEAD.replace("from apkpy_lib", "import json\nfrom apkpy_lib") + "".join(
    "\ndef case_%d():\n    %s\n    out.set_value(shown)\n" % (n, body)
    for n, body in enumerate(CASES)) + "\n" + "".join(
    'button("%d", id="b%d", command=case_%d, screen=home)\n' % (n, n + 1, n)
    for n in range(len(CASES)))


# sorted(NUMS, key=abs) puts NUMS in a name of the engine's own first
# (_apkpy_s1 = NUMS). Counted as a second name of the list, it made every
# max(NUMS) of the app text: [1, '12'].
SORTED_ELSEWHERE_APP = HEAD.replace("from apkpy_lib", "import json\nfrom apkpy_lib") + '''
NUMS = [9, 12, 10, -3, 0]


def by_size():
    out.set_value(str(sorted(NUMS, key=abs)))


def largest():
    i3 = max(NUMS)
    l = [1]
    l.append(max(len(field.get_value()), i3))
    l = l + [i3]
    out.set_value(str(l) + " " + json.dumps([i3, min(NUMS)]))


button("1", id="b1", command=by_size, screen=home)
button("2", id="b2", command=largest, screen=home)
'''


class TheItemNamesTests(unittest.TestCase):
    """The generated Java shows what CPython shows for a name given an item."""

    def test_the_same_answers_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["", "10"]
        want = _cpython(ITEMS_APP, inputs)
        self.assertIn('{"k": 5}', want)
        self.assertEqual(want, _generated(ITEMS_APP, inputs))

    def test_a_sorted_with_key_elsewhere_keeps_a_list_of_numbers(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["", "a long text here"]
        want = _cpython(SORTED_ELSEWHERE_APP, inputs)
        self.assertIn("[1, 12, 12] [12, -3]", want)
        self.assertEqual(want, _generated(SORTED_ELSEWHERE_APP, inputs))


if __name__ == "__main__":
    unittest.main()
