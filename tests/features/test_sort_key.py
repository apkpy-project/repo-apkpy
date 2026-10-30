# -*- coding: utf-8 -*-
"""sorted(key=), list.sort(key=), min(key=) and max(key=) answer as in CPython.

The Java that comes out and the refusals are held in test_python_vocabulary.py
(TheSortKeyTests). Here the generated Java runs on the PC's JVM, button by
button, next to CPython running the same app (test_classes has the two
runners). Each line is something that went wrong once: prices of 10 and 9
compared as text, keys worked out from the items before a call on the same
line reordered them, a float key that came back whole.
"""

import unittest

from test_classes import HEAD, TOOLING, _cpython, _generated

SORT_APP = HEAD.replace("from apkpy_lib", "import dataclasses\nfrom apkpy_lib") + '''
ROWS = [
    {"name": "tea", "price": 10, "qty": 2},
    {"name": "Milk", "price": 9.5, "qty": 1},
    {"name": "bread", "price": 9, "qty": 3},
    {"name": "jam", "price": 10, "qty": 1},
]


@dataclasses.dataclass
class Item:
    name: str
    price: float
    qty: int = 1


class Shelf:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)

    def cheapest(self):
        return min(self.items, key=lambda i: i.price)

    def by_qty(self):
        self.items.sort(key=lambda i: i.qty, reverse=True)
        return [i.name for i in self.items]

    def names_by_price(self):
        return [i.name for i in sorted(self.items, key=lambda i: i.price)]


class Tab:
    def __init__(self, name):
        self.name = name
        self.total = 0

    def add(self, price):
        self.total += price


def by_qty(r):
    return r["qty"]


def load():
    return list(ROWS)


def longest(groups):
    return max(groups.values(), key=len) if groups else []


def words():
    ws = ["pear", "Fig", "apple", "kiwi", "banana", "date", field.get_value() or "watermelon"]
    lines = [str(sorted(ws, key=len)), str(sorted(ws, key=str.lower)),
             str(sorted(ws, key=lambda w: w[-1], reverse=True)),
             min(ws, key=len), max(ws, key=len), str(max([], key=len, default="none"))]
    ws.sort(key=len, reverse=True)
    lines.append(str(ws))
    for name in sorted(["b", "C", "a"], key=str.lower):
        lines.append(name)
    lines.append(str(sorted("banana", key=lambda c: c)))
    lines.append(str([sorted(g, key=len) for g in [["ccc", "a"], ["bb", "dddd", "e"]]]))
    out.set_value(" | ".join(lines))


def rows():
    rs = list(ROWS)
    names = lambda found: ", ".join([r["name"] for r in found])
    lines = [names(sorted(rs, key=lambda r: r["price"])),
             names(sorted(rs, key=lambda r: r["price"], reverse=True)),
             names(sorted(rs, key=by_qty)),
             names(sorted(rs, key=lambda r: (r["price"], r["name"]))),
             names(sorted(load(), key=lambda r: r["name"].lower())),
             sorted(ROWS, key=lambda r: r["qty"])[0]["name"]]
    scores = {"ana": 7, "rui": 12, "eva": 9}
    lines.append(str(sorted(scores, key=scores.get)))
    lines.append(str([k + "=" + str(v) for k, v in
                      sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]))
    lines.append(max(scores, key=scores.get))
    lines.append(str(sorted([len(w) for w in ["ab", "abcdefghijkl", "abc"]])))
    lines.append(str(len(longest({"a": [1], "b": [1, 2, 3], "c": [4, 5]}))))
    first = sorted(rs, key=lambda r: r["name"])[0]["name"] if field.get_value() else "-"
    lines.append(first)
    out.set_value(" | ".join(lines))


def numbers():
    nums = [3, -7, 2, -1, 12]
    nums.sort(key=abs)
    lines = [str(nums), str(sorted(nums, key=lambda n: -int(n))), str(max(3, -9, 4, key=abs))]
    try:
        lines.append(str(min([], key=len)))
    except ValueError as e:
        lines.append("ValueError: " + str(e))
    out.set_value(" | ".join(lines))


def objects():
    shelf = Shelf()
    shelf.add(Item("tea", 10.0, 2))
    shelf.add(Item("milk", 9.5))
    shelf.add(Item("bread", 12.25, 3))
    shelf.add(Item(field.get_value() or "jam", 2.0, 2))
    lines = [", ".join(shelf.names_by_price()), shelf.cheapest().name,
             ", ".join(shelf.by_qty()),
             max(shelf.items, key=lambda i: i.price * i.qty).name]
    items = shelf.items
    items.sort(key=lambda i: i.name)
    lines.append(", ".join([i.name for i in items]))
    # total is 0 at first and a float later: still a number for the key.
    tabs = [Tab("x"), Tab("y"), Tab("z")]
    tabs[0].add(10.5)
    tabs[1].add(9.0)
    tabs[2].add(2.25)
    lines.append(", ".join([tab.name for tab in sorted(tabs, key=lambda tab: tab.total)]))
    out.set_value(" | ".join(lines))


button("1", id="b1", command=words, screen=home)
button("2", id="b2", command=rows, screen=home)
button("3", id="b3", command=numbers, screen=home)
button("4", id="b4", command=objects, screen=home)
'''


class TheSortAnswersTests(unittest.TestCase):
    """The generated Java orders what CPython orders, button by button."""

    def test_the_same_order_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["apple", ""]
        self.assertEqual(_cpython(SORT_APP, inputs), _generated(SORT_APP, inputs))


if __name__ == "__main__":
    unittest.main()
